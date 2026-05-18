import os
import sys
import json
import time
import signal
import threading
import subprocess
import re
from urllib import request, error
from pathlib import Path


LOG_FILE = Path(__file__).parent / "chat-log" / "log.txt"
WORKSPACE_ROOT = Path(__file__).parent / "workspace"
WORKSPACE_ROOT.mkdir(exist_ok=True)

SKILLS_ROOT = Path(__file__).parent.parent / ".agents" / "skills"
if not SKILLS_ROOT.exists():
    SKILLS_ROOT = Path(__file__).parent / ".agents" / "skills"
if not SKILLS_ROOT.exists():
    SKILLS_ROOT = Path.cwd() / ".agents" / "skills"
if not SKILLS_ROOT.exists():
    SKILLS_ROOT = Path.cwd().parent / ".agents" / "skills"


class ChainedCallContext:
    def __init__(self, user_request: str, max_iterations: int = 10):
        self.user_request = user_request
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.execution_history = []
        self.context_variables = {}
        self.final_answer = None
        self.is_completed = False
        self.error = None
    
    def add_tool_execution(self, tool_name: str, arguments: dict, result: dict):
        truncated_result = {}
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 500:
                if 'content' in key.lower() and tool_name in ['curl_request', 'extract_text_from_html']:
                    truncated_result[key] = value[:200] + f"...[内容已摘要, 原长度 {len(value)} 字符]"
                else:
                    truncated_result[key] = value[:500] + f"...[已截断, 原长度 {len(value)} 字符]"
            else:
                truncated_result[key] = value
        
        execution_record = {
            "step": len(self.execution_history) + 1,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": truncated_result,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.execution_history.append(execution_record)
        result_key = f"step_{len(self.execution_history)}_{tool_name}_result"
        self.context_variables[result_key] = result
        return execution_record
    
    def can_continue(self) -> bool:
        if self.is_completed:
            return False
        if self.current_iteration >= self.max_iterations:
            self.error = f"已达到最大迭代次数 {self.max_iterations}"
            return False
        return True
    
    def increment_iteration(self):
        self.current_iteration += 1
    
    def get_execution_summary(self) -> str:
        if not self.execution_history:
            return "尚未执行任何工具调用"
        
        summary_lines = ["已执行的工具调用历史:"]
        for record in self.execution_history:
            summary_lines.append(f"\n步骤 {record['step']}: {record['tool_name']}")
            if record['arguments']:
                args_str = json.dumps(record['arguments'], ensure_ascii=False)
                if len(args_str) > 100:
                    args_str = args_str[:100] + "..."
                summary_lines.append(f"  参数: {args_str}")
            result_str = json.dumps(record['result'], ensure_ascii=False)
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."
            summary_lines.append(f"  结果: {result_str}")
        
        return "\n".join(summary_lines)
    
    def mark_completed(self, answer: str):
        self.is_completed = True
        self.final_answer = answer
    
    def to_dict(self) -> dict:
        return {
            "user_request": self.user_request,
            "max_iterations": self.max_iterations,
            "current_iteration": self.current_iteration,
            "execution_history": self.execution_history,
            "context_variables": list(self.context_variables.keys()),
            "is_completed": self.is_completed,
            "final_answer": self.final_answer,
            "error": self.error
        }


def build_analysis_prompt(context: ChainedCallContext) -> str:
    var_list = ", ".join(list(context.context_variables.keys()))
    
    prompt = f"""链式工具调用决策

请求: {context.user_request}
步骤: {context.current_iteration}/{context.max_iterations}
{context.get_execution_summary()}
可用变量: {var_list}

=== 网页处理必用流程 ===
curl_request → extract_text_from_html → summarize_text_content → create_file(directory='')
⚠️ create_file 的 directory 参数传空字符串 ''

=== 批量工具优先 ===
多文件: search_files_by_content → batch_read_files → summarize_files_content
多网页: batch_web_fetch

=== 变量引用 ===
使用 ${{step_N_tool_name_result['key']}} 引用之前结果，支持 Python 表达式。

=== 输出格式 ===
完成: {{"done": true, "answer": "..."}}
继续: {{"done": false, "tool_call": {{"name": "", "arguments": {{}}}}}}
"""
    return prompt


def resolve_context_variables(value: str, context: ChainedCallContext) -> any:
    if isinstance(value, str):
        if '${' in value and '}' in value:
            eval_env = {}
            for var_name, var_value in context.context_variables.items():
                eval_env[var_name] = var_value
            
            expression = value.strip()
            if expression.startswith('${') and expression.endswith('}'):
                expression = expression[2:-1].strip()
            
            try:
                resolved_value = eval(expression, eval_env)
                print(f"[变量解析] 表达式: {expression}")
                print(f"[变量解析] 结果类型: {type(resolved_value).__name__}, 长度: {len(str(resolved_value))}")
                return resolved_value
            except Exception as e:
                print(f"[变量解析失败] 表达式: {expression}")
                print(f"[变量解析失败] 错误: {str(e)}")
                print(f"[变量解析失败] 可用变量: {list(eval_env.keys())}")
                return value
    
    if isinstance(value, list):
        return [resolve_context_variables(item, context) for item in value]
    elif isinstance(value, dict):
        return {k: resolve_context_variables(v, context) for k, v in value.items()}
    
    return value


def resolve_arguments(arguments: dict, context: ChainedCallContext) -> dict:
    resolved = {}
    for key, value in arguments.items():
        resolved[key] = resolve_context_variables(value, context)
    return resolved


def parse_llm_decision(response_text: str) -> dict:
    try:
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            json_text = json_match.group(0)
            return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass
    
    return {
        "done": True,
        "answer": response_text
    }


def execute_chained_tool_call(env, user_request: str, max_iterations: int = 10) -> dict:
    context = ChainedCallContext(user_request, max_iterations)
    
    print(f"\n[链式调用] 开始处理: {user_request[:50]}...")
    print(f"[链式调用] 最大迭代次数: {max_iterations}")
    
    while context.can_continue():
        context.increment_iteration()
        print(f"\n[链式调用] 第 {context.current_iteration} 轮决策...")
        
        analysis_prompt = build_analysis_prompt(context)
        
        decision_messages = [
            {"role": "user", "content": analysis_prompt}
        ]
        
        try:
            llm_response = call_llm_simple(env, decision_messages)
            decision = parse_llm_decision(llm_response)
        except Exception as e:
            context.error = f"LLM 决策失败: {str(e)}"
            break
        
        if decision.get("done", True):
            answer = decision.get("answer", "任务完成")
            context.mark_completed(answer)
            print(f"[链式调用] 任务完成！")
            break
        
        tool_call = decision.get("tool_call", {})
        tool_name = tool_call.get("name", "")
        arguments = tool_call.get("arguments", {})
        
        if not tool_name:
            context.error = "决策中缺少工具名称"
            break
        
        resolved_arguments = resolve_arguments(arguments, context)
        
        print(f"[链式调用] 执行工具: {tool_name}")
        print(f"[链式调用] 解析前参数: {json.dumps(arguments, ensure_ascii=False)}")
        print(f"[链式调用] 解析后参数: {json.dumps(resolved_arguments, ensure_ascii=False)}")
        
        for key, value in resolved_arguments.items():
            if isinstance(value, str) and len(value.strip()) < 5 and 'content' in key:
                print(f"[警告] {key} 内容过短，可能解析失败！")
                print(f"  可用上下文变量: {list(context.context_variables.keys())}")
        
        func = FUNCTION_MAP.get(tool_name)
        if not func:
            context.error = f"未知工具函数: {tool_name}"
            break
        
        try:
            result = func(**resolved_arguments)
            result = _convert_bytes(result)
            context.add_tool_execution(tool_name, resolved_arguments, result)
            print(f"[链式调用] 执行完成")
        except Exception as e:
            context.error = f"执行工具 {tool_name} 失败: {str(e)}"
            break
    
    if context.error:
        print(f"[链式调用] 错误: {context.error}")
    
    print(f"[链式调用] 总共执行 {len(context.execution_history)} 步")
    
    return context.to_dict()


def load_env():
    possible_paths = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent / ".env",
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
    ]
    
    env_path = None
    for p in possible_paths:
        if p.exists():
            env_path = p
            break
    
    if not env_path:
        raise FileNotFoundError(f"未找到 .env 文件，请先将 env.example 复制为 .env 并填写配置\n搜索路径：{[str(p) for p in possible_paths]}")
    
    env_vars = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars


def print_stream(content):
    sys.stdout.write(content)
    sys.stdout.flush()


def ensure_log_file():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("=== 聊天关键信息记录 ===\n\n")


def append_to_log(content):
    ensure_log_file()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(content + "\n")


def read_chat_log():
    ensure_log_file()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read()


def list_available_skills() -> dict:
    if not SKILLS_ROOT.exists():
        return {"error": f"技能目录不存在: {SKILLS_ROOT}", "skills": []}
    
    skills = []
    
    for skill_dir in SKILLS_ROOT.iterdir():
        if not skill_dir.is_dir():
            continue
        
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        
        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
            
            front_matter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if front_matter_match:
                front_matter_content = front_matter_match.group(1)
                
                name = None
                description = None
                
                for line in front_matter_content.split("\n"):
                    line = line.strip()
                    if line.startswith("name:"):
                        name = line[5:].strip().strip('"').strip("'")
                    elif line.startswith("description:"):
                        description = line[12:].strip().strip('"').strip("'")
                
                if name and description:
                    skills.append({
                        "name": name,
                        "description": description
                    })
        
        except Exception as e:
            print(f"[警告] 读取技能 {skill_dir.name} 失败: {e}")
            continue
    
    return {
        "success": True,
        "skills": skills,
        "total": len(skills)
    }


def load_skill_content(skill_name: str) -> dict:
    if not SKILLS_ROOT.exists():
        return {"error": f"技能目录不存在: {SKILLS_ROOT}"}
    
    skill_name_normalized = skill_name.strip().lower()
    
    for skill_dir in SKILLS_ROOT.iterdir():
        if not skill_dir.is_dir():
            continue
        
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        
        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
            
            front_matter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not front_matter_match:
                continue
            
            front_matter_content = front_matter_match.group(1)
            
            name = None
            for line in front_matter_content.split("\n"):
                line = line.strip()
                if line.startswith("name:"):
                    name = line[5:].strip().strip('"').strip("'").lower()
                    break
            
            if name == skill_name_normalized or skill_dir.name.lower() == skill_name_normalized:
                main_content = content[front_matter_match.end():].strip()
                
                return {
                    "success": True,
                    "skill_name": skill_name,
                    "skill_directory": skill_dir.name,
                    "content": main_content
                }
        
        except Exception as e:
            return {"error": f"读取技能内容失败: {str(e)}"}
    
    return {"error": f"未找到技能: {skill_name}"}


def anythingllm_get_workspaces() -> dict:
    env = load_env()
    api_key = env.get("ANYTHINGLLM_API_KEY")
    
    if not api_key:
        return {"error": "未配置 ANYTHINGLLM_API_KEY，请在 .env 文件中配置"}
    
    url = "http://localhost:3001/api/v1/workspaces"
    
    curl_cmd = [
        "curl.exe", "-s", "-X", "GET", url,
        "-H", f"Authorization: Bearer {api_key}",
        "-H", "Content-Type: application/json"
    ]
    
    try:
        result = subprocess.run(
            curl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )
        
        stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ''
        
        if result.returncode != 0:
            return {"error": f"curl执行失败 (退出码: {result.returncode})"}
        
        try:
            response_data = json.loads(stdout)
            workspaces = []
            for ws in response_data.get("workspaces", []):
                workspaces.append({
                    "id": ws.get("id"),
                    "name": ws.get("name"),
                    "slug": ws.get("slug")
                })
            return {
                "success": True,
                "workspaces": workspaces,
                "default_slug": workspaces[0].get("slug") if workspaces else None
            }
        except json.JSONDecodeError:
            return {"error": "API返回结果解析失败", "raw": stdout[:200]}
            
    except Exception as e:
        return {"error": f"调用失败: {str(e)}"}


def anythingllm_list_documents(workspace_slug: str = None) -> dict:
    env = load_env()
    api_key = env.get("ANYTHINGLLM_API_KEY")
    
    if not api_key:
        return {"error": "未配置 ANYTHINGLLM_API_KEY，请在 .env 文件中配置"}
    
    if not workspace_slug:
        workspace_slug = env.get("ANYTHINGLLM_WORKSPACE_SLUG")
    
    if not workspace_slug:
        ws_result = anythingllm_get_workspaces()
        if ws_result.get("success") and ws_result.get("default_slug"):
            workspace_slug = ws_result["default_slug"]
        else:
            return {"error": "无法获取工作区列表，请在.env配置ANYTHINGLLM_WORKSPACE_SLUG或手动指定"}
    
    url = f"http://localhost:3001/api/v1/workspace/{workspace_slug}"
    
    curl_cmd = [
        "curl.exe", "-s", "-X", "GET", url,
        "-H", f"Authorization: Bearer {api_key}",
        "-H", "Content-Type: application/json"
    ]
    
    try:
        result = subprocess.run(
            curl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )
        
        stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ''
        
        if result.returncode != 0:
            return {"error": f"curl执行失败 (退出码: {result.returncode})"}
        
        try:
            response_data = json.loads(stdout)
            workspaces = response_data.get("workspace", [])
            if not workspaces:
                return {"error": "未找到工作区信息", "workspace_slug": workspace_slug}
            
            workspace = workspaces[0]
            workspace_name = workspace.get("name")
            documents = workspace.get("documents", [])
            
            document_list = []
            for doc in documents:
                document_list.append({
                    "id": doc.get("id"),
                    "name": doc.get("name", doc.get("title", doc.get("filename", "未命名"))),
                    "type": doc.get("type"),
                    "source": doc.get("docSource"),
                    "word_count": doc.get("wordCount", 0),
                    "tokens": doc.get("token_count_estimate", 0)
                })
            
            return {
                "success": True,
                "workspace": workspace_name,
                "workspace_slug": workspace_slug,
                "total_documents": len(document_list),
                "documents": document_list
            }
        except json.JSONDecodeError:
            return {
                "error": "API返回结果解析失败",
                "raw_response": stdout[:500]
            }
            
    except subprocess.TimeoutExpired:
        return {"error": "API请求超时"}
    except Exception as e:
        return {"error": f"调用失败: {str(e)}"}


def anythingllm_query(message: str, workspace_slug: str = None) -> dict:
    env = load_env()
    api_key = env.get("ANYTHINGLLM_API_KEY")
    
    if not api_key:
        return {"error": "未配置 ANYTHINGLLM_API_KEY，请在 .env 文件中配置"}
    
    if not workspace_slug:
        workspace_slug = env.get("ANYTHINGLLM_WORKSPACE_SLUG")
    
    if not workspace_slug:
        ws_result = anythingllm_get_workspaces()
        if ws_result.get("success") and ws_result.get("default_slug"):
            workspace_slug = ws_result["default_slug"]
        else:
            return {"error": "无法获取工作区列表，请在.env配置ANYTHINGLLM_WORKSPACE_SLUG或手动指定"}
    
    url = f"http://localhost:3001/api/v1/workspace/{workspace_slug}/chat"
    
    payload = {
        "message": message,
        "mode": "query"
    }
    
    payload_json = json.dumps(payload, ensure_ascii=False)
    
    curl_cmd = [
        "curl.exe", "-s", "-X", "POST", url,
        "-H", f"Authorization: Bearer {api_key}",
        "-H", "Content-Type: application/json",
        "-d", payload_json
    ]
    
    try:
        result = subprocess.run(
            curl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60
        )
        
        stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ''
        
        if result.returncode != 0:
            return {"error": f"curl执行失败 (退出码: {result.returncode})"}
        
        try:
            response_data = json.loads(stdout)
            return {
                "success": True,
                "workspace": workspace_slug,
                "query": message,
                "response": response_data.get("textResponse", ""),
                "sources": response_data.get("sources", []),
                "metadata": {
                    "close": response_data.get("close", False),
                    "error": response_data.get("error", None),
                    "id": response_data.get("id", "")
                }
            }
        except json.JSONDecodeError:
            return {
                "error": "API返回结果解析失败",
                "raw_response": stdout[:500]
            }
            
    except subprocess.TimeoutExpired:
        return {"error": "API请求超时"}
    except Exception as e:
        return {"error": f"调用失败: {str(e)}"}


def search_chat_history(env, query):
    print(f"[系统] 正在检索本地聊天历史记录...")
    history_log = read_chat_log()
    
    if len(history_log) > 8000:
        entries = history_log.split("===")
        recent = entries[-20:]
        history_log = "===".join(recent)
        print(f"[系统] 日志过长，仅检索最近 {len(recent)-1} 条记忆")
    
    if not query.strip():
        query = "总结一下最近的聊天历史"
    
    full_prompt = f"""请你作为聊天历史助手，基于以下聊天历史记录回答我的问题。

聊天历史记录（最近）：
{history_log[:8000]}

我的问题：{query}

请根据上面的历史记录，准确、清晰地回答问题。如果历史记录中没有相关信息，请如实说明。"""
    
    return [
        {"role": "user", "content": full_prompt}
    ]


def list_directory(directory_path: str = ".") -> dict:
    project_root = Path(__file__).parent.parent.resolve()
    target_path = (project_root / directory_path).resolve()
    
    if not str(target_path).startswith(str(project_root)):
        return {"error": "超出项目目录范围，操作被拒绝"}
    
    if not target_path.exists():
        return {"error": f"目录不存在: {directory_path}"}
    
    if not target_path.is_dir():
        return {"error": f"不是目录: {directory_path}"}
    
    result = {
        "directory": str(target_path.relative_to(project_root)),
        "items": []
    }
    
    for item in target_path.iterdir():
        stat = item.stat()
        item_info = {
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size_bytes": stat.st_size if item.is_file() else None,
            "modified_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        }
        result["items"].append(item_info)
    
    result["total_items"] = len(result["items"])
    return result


def rename_file(directory: str, old_name: str, new_name: str) -> dict:
    project_root = Path(__file__).parent.parent.resolve()
    target_dir = (project_root / directory).resolve()
    
    if not str(target_dir).startswith(str(project_root)):
        return {"error": "超出项目目录范围，操作被拒绝"}
    
    old_path = target_dir / old_name
    new_path = target_dir / new_name
    
    if not old_path.exists():
        return {"error": f"文件不存在: {old_name}"}
    
    if new_path.exists():
        return {"error": f"新文件名已存在: {new_name}"}
    
    try:
        old_path.rename(new_path)
        return {
            "success": True,
            "message": f"文件重命名成功",
            "old_name": old_name,
            "new_name": new_name
        }
    except Exception as e:
        return {"error": f"重命名失败: {str(e)}"}


def delete_file(directory: str, filename: str) -> dict:
    project_root = Path(__file__).parent.parent.resolve()
    target_dir = (project_root / directory).resolve()
    
    if not str(target_dir).startswith(str(project_root)):
        return {"error": "超出项目目录范围，操作被拒绝"}
    
    file_path = target_dir / filename
    
    if not file_path.exists():
        return {"error": f"文件不存在: {filename}"}
    
    if not file_path.is_file():
        return {"error": f"不是文件: {filename}"}
    
    try:
        file_path.unlink()
        return {
            "success": True,
            "message": f"文件删除成功: {filename}"
        }
    except Exception as e:
        return {"error": f"删除失败: {str(e)}"}


def create_file(directory: str, filename: str, content: str = "") -> dict:
    script_dir = Path(__file__).parent.resolve()
    
    if directory and directory.strip():
        target_dir = (script_dir / directory).resolve()
    else:
        target_dir = script_dir.resolve()
    
    if not str(target_dir).startswith(str(script_dir)):
        return {"error": "超出当前目录范围，操作被拒绝"}
    
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / filename
    
    if not content or not content.strip():
        print(f"[警告] 文件内容为空，将创建空文件: {filename}")
        print(f"  目标路径: {file_path}")
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        action = "覆盖" if file_path.exists() else "创建"
        print(f"[{action}文件] 路径: {file_path}, 大小: {len(content.encode('utf-8'))} 字节")
        
        return {
            "success": True,
            "message": f"文件{action}成功: {file_path}",
            "full_path": str(file_path),
            "size_bytes": len(content.encode("utf-8"))
        }
    except Exception as e:
        return {"error": f"写入文件失败: {str(e)}"}


def read_file(directory: str, filename: str) -> dict:
    project_root = Path(__file__).parent.parent.resolve()
    target_dir = (project_root / directory).resolve()
    
    if not str(target_dir).startswith(str(project_root)):
        return {"error": "超出项目目录范围，操作被拒绝"}
    
    file_path = target_dir / filename
    
    if not file_path.exists():
        return {"error": f"文件不存在: {filename}"}
    
    if not file_path.is_file():
        return {"error": f"不是文件: {filename}"}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return {
            "success": True,
            "filename": filename,
            "content": content,
            "size_bytes": len(content.encode("utf-8"))
        }
    except Exception as e:
        return {"error": f"读取文件失败: {str(e)}"}


def extract_text_from_html(html_content: str = "", text: str = "", content: str = "") -> dict:
    actual_content = html_content or text or content
    if not actual_content:
        return {"error": "缺少 html_content 参数"}
    
    try:
        html_patterns = [
            (r'<script[\s\S]*?</script>', ''),
            (r'<style[\s\S]*?</style>', ''),
            (r'<[^>]+>', ' '),
            (r'\s+', ' '),
        ]
        
        processed_text = actual_content
        for pattern, repl in html_patterns:
            processed_text = re.sub(pattern, repl, processed_text, flags=re.IGNORECASE)
        
        lines = [line.strip() for line in processed_text.split('\n') if line.strip()]
        clean_text = '\n'.join(lines)
        
        return {
            "success": True,
            "original_length": len(actual_content),
            "text_length": len(clean_text),
            "content": clean_text[:10000],
            "truncated": len(clean_text) > 10000
        }
    except Exception as e:
        return {"error": f"HTML提取失败: {str(e)}"}


def summarize_text_content(text: str = "", content: str = "", html_content: str = "", max_length: int = 500) -> dict:
    actual_text = text or content or html_content
    if not actual_text or not actual_text.strip():
        return {"error": "文本内容为空"}
    
    try:
        sentences = re.split(r'[。！？.!?]', actual_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 3:
            summary = actual_text[:max_length]
        else:
            key_sentences = []
            keywords = ['重要', '关键', '主要', '核心', '成功', '失败', '结果', 
                       '研究', '发现', '结论', 'successful', 'important', 'key', 
                       'result', 'conclusion', 'breakthrough']
            
            for i, s in enumerate(sentences):
                if i < 2 or i >= len(sentences) - 1:
                    key_sentences.append(s)
                    continue
                for kw in keywords:
                    if kw in s:
                        key_sentences.append(s)
                        break
            
            summary = '。'.join(key_sentences)
            if len(summary) > max_length:
                summary = summary[:max_length] + "..."
        
        return {
            "success": True,
            "original_length": len(actual_text),
            "summary_length": len(summary),
            "original_sentences": len(sentences),
            "summary_sentences": summary.count('。') + summary.count('！') + summary.count('？'),
            "summary": summary
        }
    except Exception as e:
        return {"error": f"文本摘要失败: {str(e)}"}


def get_current_datetime() -> dict:
    now = time.localtime()
    return {
        "success": True,
        "year": now.tm_year,
        "month": now.tm_mon,
        "day": now.tm_mday,
        "hour": now.tm_hour,
        "minute": now.tm_min,
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.tm_wday],
        "date": time.strftime("%Y-%m-%d", now),
        "time": time.strftime("%H:%M:%S", now),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S %A", now)
    }


def curl_request(url: str, method: str = "GET", timeout: int = 30) -> dict:
    if not url.startswith(("http://", "https://")):
        return {"error": "URL 必须以 http:// 或 https:// 开头"}
    
    try:
        start_time = time.time()
        
        req = request.Request(url, method=method.upper())
        req.add_header("User-Agent", "curl/7.68.0")
        req.add_header("Accept", "*/*")
        
        with request.urlopen(req, timeout=timeout) as response:
            content_bytes = response.read()
            elapsed_time = time.time() - start_time
            
            content_type = response.headers.get("Content-Type", "")
            
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
                try:
                    content = content_bytes.decode(charset)
                except:
                    content = content_bytes.decode("utf-8", errors="ignore")
            else:
                content = content_bytes.decode("utf-8", errors="ignore")
            
            if "text" in content_type or content_type == "":
                max_content = 20000
            else:
                max_content = 5000
            
            content_truncated = content[:max_content]
            truncated = len(content) > max_content
            
            return {
                "success": True,
                "url": url,
                "method": method,
                "status_code": response.status,
                "content_type": content_type,
                "content": content_truncated,
                "content_length": len(content_bytes),
                "truncated": truncated,
                "elapsed_time": round(elapsed_time, 2)
            }
            
    except error.HTTPError as e:
        return {"error": f"HTTP 错误: {e.code}", "status_code": e.code}
    except error.URLError as e:
        return {"error": f"网络连接失败: {e.reason}"}
    except Exception as e:
        return {"error": f"请求失败: {str(e)}"}


def find_files(directory_path: str = ".", pattern: str = "*.py", max_depth: int = 3) -> dict:
    project_root = Path(__file__).parent.parent.resolve()
    target_path = (project_root / directory_path).resolve()
    
    if not str(target_path).startswith(str(project_root)):
        return {"error": "超出项目目录范围，操作被拒绝"}
    
    if not target_path.exists():
        return {"error": f"目录不存在: {directory_path}"}
    
    if not target_path.is_dir():
        return {"error": f"不是目录: {directory_path}"}
    
    import fnmatch
    
    matched_files = []
    
    def scan_dir(current_path, current_depth):
        if current_depth > max_depth:
            return
        
        for item in current_path.iterdir():
            if item.is_dir():
                scan_dir(item, current_depth + 1)
            elif item.is_file():
                rel_path = str(item.relative_to(project_root))
                if fnmatch.fnmatch(item.name, pattern):
                    stat = item.stat()
                    matched_files.append({
                        "path": rel_path,
                        "name": item.name,
                        "size_bytes": stat.st_size,
                        "modified_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                    })
    
    scan_dir(target_path, 0)
    
    return {
        "success": True,
        "directory": str(target_path.relative_to(project_root)),
        "pattern": pattern,
        "max_depth": max_depth,
        "total_matched": len(matched_files),
        "files": matched_files
    }


def search_files_by_content(directory_path: str = ".", keyword: str = "def", 
                           file_pattern: str = "*.py", max_depth: int = 3) -> dict:
    project_root = Path(__file__).parent.parent.resolve()
    target_path = (project_root / directory_path).resolve()
    
    if not str(target_path).startswith(str(project_root)):
        return {"error": "超出项目目录范围，操作被拒绝"}
    
    files_result = find_files(directory_path, file_pattern, max_depth)
    if "error" in files_result:
        return files_result
    
    keyword_lower = keyword.lower()
    matching_files = []
    
    for file_info in files_result.get("files", []):
        file_full_path = WORKSPACE_ROOT / file_info["path"]
        
        try:
            with open(file_full_path, "r", encoding="utf-8") as f:
                content = f.read().lower()
                
            if keyword_lower in content:
                line_numbers = []
                with open(file_full_path, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if keyword_lower in line.lower():
                            line_numbers.append(i)
                            if len(line_numbers) >= 10:
                                break
                
                matching_files.append({
                    "path": file_info["path"],
                    "name": file_info["name"],
                    "size_bytes": file_info["size_bytes"],
                    "matching_lines_count": content.count(keyword_lower),
                    "sample_line_numbers": line_numbers
                })
        except:
            continue
    
    return {
        "success": True,
        "keyword": keyword,
        "file_pattern": file_pattern,
        "total_searched": files_result.get("total_matched", 0),
        "total_matching": len(matching_files),
        "matching_files": matching_files
    }


def batch_read_files(file_paths: list, directory: str = None) -> dict:
    project_root = Path(__file__).parent.parent.resolve()
    
    results = []
    failed = []
    
    for rel_path in file_paths:
        file_path = project_root / rel_path
        
        if not file_path.exists():
            failed.append({"path": rel_path, "error": "文件不存在"})
            continue
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            results.append({
                "path": rel_path,
                "success": True,
                "content": content[:5000],
                "size_bytes": len(content),
                "truncated": len(content) > 5000
            })
        except Exception as e:
            failed.append({"path": rel_path, "error": str(e)})
    
    return {
        "success": True,
        "total_requested": len(file_paths),
        "success_count": len(results),
        "failed_count": len(failed),
        "results": results,
        "failed": failed
    }


def batch_web_fetch(urls: list) -> dict:
    results = []
    failed = []
    
    for url in urls:
        result = curl_request(url)
        if result.get("success"):
            results.append({
                "url": url,
                "status_code": result.get("status_code"),
                "content_preview": result.get("content", "")[:1000] + ("..." if len(result.get("content", "")) > 1000 else "")
            })
        else:
            failed.append({"url": url, "error": result.get("error")})
    
    return {
        "success": True,
        "total_requested": len(urls),
        "success_count": len(results),
        "failed_count": len(failed),
        "results": results,
        "failed": failed
    }


def summarize_files_content(files_data: list) -> dict:
    summaries = []
    
    for file_data in files_data:
        content = file_data.get("content", "")
        path = file_data.get("path", "")
        
        lines = content.strip().split("\n")
        imports = [line for line in lines[:50] if line.startswith("import ") or line.startswith("from ")]
        functions = [line for line in lines if line.strip().startswith("def ")]
        classes = [line for line in lines if line.strip().startswith("class ")]
        
        summary = {
            "file": path,
            "total_lines": len(lines),
            "imports_count": len(imports),
            "functions_count": len(functions),
            "classes_count": len(classes),
            "sample_functions": functions[:5],
            "sample_classes": classes[:3]
        }
        summaries.append(summary)
    
    return {
        "success": True,
        "total_files": len(summaries),
        "summaries": summaries
    }


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_available_skills",
            "description": "列出系统中所有可用的技能插件，包含技能名称和描述。当用户询问有什么技能、可以做什么、有什么功能时，或者当你判断用户的问题可能需要使用特定技能时，请调用此工具获取可用技能列表。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "load_skill_content",
            "description": "加载指定技能的详细使用说明和执行步骤。当用户的问题明确需要使用某个特定技能时，或者当你通过 list_available_skills 了解可用技能后，判断需要调用某个技能时，请使用此工具加载该技能的详细内容。加载后，请严格按照技能说明执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "要加载的技能名称，如 'notice' 或其他技能名称"
                    }
                },
                "required": ["skill_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "anythingllm_list_documents",
            "description": "列出AnythingLLM工作区中的所有文档文件。当用户询问仓库有什么文件、列出知识库文档、查看所有文件时，必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_slug": {
                        "type": "string",
                        "description": "AnythingLLM工作区slug，不填则自动使用默认工作区"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "anythingllm_query",
            "description": "查询AnythingLLM知识库，从文档仓库中检索相关信息。当用户提到文档仓库、文件仓库、仓库、知识库、查文档时，必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "用户要查询的问题内容"
                    },
                    "workspace_slug": {
                        "type": "string",
                        "description": "AnythingLLM工作区slug，不填则自动使用默认工作区"
                    }
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出指定目录下的所有文件和子目录，包含文件大小、修改时间等基本属性",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "要列出的目录路径，相对于工作区根目录，默认为当前目录"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "修改指定目录下某个文件的名称",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在的目录路径"
                    },
                    "old_name": {
                        "type": "string",
                        "description": "原来的文件名"
                    },
                    "new_name": {
                        "type": "string",
                        "description": "新的文件名"
                    }
                },
                "required": ["directory", "old_name", "new_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除指定目录下的某个文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在的目录路径"
                    },
                    "filename": {
                        "type": "string",
                        "description": "要删除的文件名"
                    }
                },
                "required": ["directory", "filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "在指定目录下新建一个文件，并且可以写入初始内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "目标目录路径"
                    },
                    "filename": {
                        "type": "string",
                        "description": "要创建的文件名"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文件内容，默认为空字符串"
                    }
                },
                "required": ["directory", "filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定目录下某个文件的全部内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "文件所在的目录路径"
                    },
                    "filename": {
                        "type": "string",
                        "description": "要读取的文件名"
                    }
                },
                "required": ["directory", "filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "获取当前系统日期和时间。当用户询问今天几号、现在几点、星期几、当前时间，或者需要知道当前日期时间才能回答问题时，必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "curl_request",
            "description": "模拟curl访问网页获取内容或数据。支持返回完整的ANSI艺术字符，用于天气图等。查询天气、实时信息、最新数据或者任何需要联网才能获取的信息时，必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要访问的完整URL地址，如：https://wttr.in/成都 (天气图)、https://wttr.in/青城山?format=j1 (JSON)"
                    },
                    "method": {
                        "type": "string",
                        "description": "HTTP方法，可选：GET/POST"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时时间秒数，可选"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "递归搜索指定目录下符合通配符模式的所有文件。支持按扩展名、文件名模式搜索。需要查找多个文件、按类型筛选文件时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "要搜索的目录路径，默认为当前目录"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "文件匹配模式，如: *.py、*.txt、*.md 等"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "递归搜索的最大深度，默认3层"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files_by_content",
            "description": "搜索目录下所有文件内容中包含指定关键词的文件。需要查找包含特定内容的多个文件时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "要搜索的目录路径"
                    },
                    "keyword": {
                        "type": "string",
                        "description": "要搜索的内容关键词"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "文件匹配模式，如: *.py"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "递归深度"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_read_files",
            "description": "一次性批量读取多个文件的内容。需要同时处理多个文件时使用此工具，避免逐个读取。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要读取的文件路径列表，如: [\"file1.py\", \"file2.py\"]"
                    },
                    "directory": {
                        "type": "string",
                        "description": "文件所在的根目录路径"
                    }
                },
                "required": ["file_paths"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "batch_web_fetch",
            "description": "批量获取多个网页的内容。需要同时爬取多个网址数据时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "网址列表，如: [\"http://url1.com\", \"http://url2.com\"]"
                    }
                },
                "required": ["urls"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_files_content",
            "description": "对多个文件的内容进行结构化摘要统计。批量读取文件后，使用此工具快速汇总文件特征。",
            "parameters": {
                "type": "object",
                "properties": {
                    "files_data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "batch_read_files 返回的 results 数组"
                    }
                },
                "required": ["files_data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_text_from_html",
            "description": "从 HTML 内容中提取纯文本，自动移除 script、style 和 HTML 标签。获取网页后必须调用此工具提取可读内容！",
            "parameters": {
                "type": "object",
                "properties": {
                    "html_content": {
                        "type": "string",
                        "description": "curl_request 返回的 HTML 内容字符串"
                    }
                },
                "required": ["html_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_text_content",
            "description": "自动生成文本内容摘要。提取网页或长文本后，必须调用此工具生成精简摘要再保存或展示。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "需要摘要的长文本内容"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "摘要最大长度，默认500字"
                    }
                },
                "required": ["text"]
            }
        }
    }
]


FUNCTION_MAP = {
    "list_available_skills": list_available_skills,
    "load_skill_content": load_skill_content,
    "anythingllm_get_workspaces": anythingllm_get_workspaces,
    "anythingllm_list_documents": anythingllm_list_documents,
    "anythingllm_query": anythingllm_query,
    "list_directory": list_directory,
    "rename_file": rename_file,
    "delete_file": delete_file,
    "create_file": create_file,
    "read_file": read_file,
    "get_current_datetime": get_current_datetime,
    "curl_request": curl_request,
    "find_files": find_files,
    "search_files_by_content": search_files_by_content,
    "batch_read_files": batch_read_files,
    "batch_web_fetch": batch_web_fetch,
    "summarize_files_content": summarize_files_content,
    "extract_text_from_html": extract_text_from_html,
    "summarize_text_content": summarize_text_content
}


def call_llm_simple(env, messages, stream=False):
    base_url = env.get("BASE_URL", env.get("LLM_BASE_URL", "")).rstrip("/")
    api_key = env.get("API_KEY", env.get("LLM_API_KEY", ""))
    model = env.get("MODEL", env.get("LLM_MODEL", "gpt-3.5-turbo"))
    
    if not base_url or not api_key:
        raise ValueError("请在 .env 文件中配置 LLM_BASE_URL 和 LLM_API_KEY")
    
    url = f"{base_url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(env.get("LLM_TEMPERATURE", "0.3")),
        "stream": stream,
    }
    
    if "LLM_MAX_TOKENS" in env:
        payload["max_tokens"] = int(env["LLM_MAX_TOKENS"])
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    timeout = int(env.get("LLM_TIMEOUT", "300"))
    
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    
    if len(data) > 100000:
        print(f"[警告] 请求内容过大: {len(data)} 字节，可能触发 400 错误")
    
    if not stream:
        try:
            with request.urlopen(req, timeout=timeout) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                return response_data["choices"][0]["message"]["content"]
        except request.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            print(f"[LLM 错误] HTTP {e.code}: {e.reason}")
            print(f"[LLM 错误] 响应内容: {error_body[:500]}")
            raise Exception(f"HTTP {e.code}: {e.reason} - {error_body[:200]}")
    else:
        full_response = ""
        try:
            with request.urlopen(req, timeout=timeout) as response:
                for line in response:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            chunk_data = json.loads(line[6:])
                            delta = chunk_data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_response += content
                        except:
                            continue
        except request.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            print(f"[LLM 错误] HTTP {e.code}: {e.reason}")
            print(f"[LLM 错误] 响应内容: {error_body[:500]}")
            raise Exception(f"HTTP {e.code}: {e.reason}")
        return full_response


def call_llm_final_answer_stream(env, messages):
    base_url = env.get("BASE_URL", env.get("LLM_BASE_URL", "")).rstrip("/")
    api_key = env.get("API_KEY", env.get("LLM_API_KEY", ""))
    model = env.get("MODEL", env.get("LLM_MODEL", "gpt-3.5-turbo"))
    
    if not base_url or not api_key:
        raise ValueError("请在 .env 文件中配置 LLM_BASE_URL 和 LLM_API_KEY")
    
    url = f"{base_url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(env.get("LLM_TEMPERATURE", "0.7")),
        "stream": True,
    }
    
    if "LLM_MAX_TOKENS" in env:
        payload["max_tokens"] = int(env["LLM_MAX_TOKENS"])
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    timeout = int(env.get("LLM_TIMEOUT", "120"))
    
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    
    full_response = ""
    token_count = 0
    start_time = time.time()
    
    with request.urlopen(req, timeout=timeout) as response:
        print_stream("\n[AI] ")
        
        for line in response:
            line = line.decode("utf-8").strip()
            
            if not line or line == "data: [DONE]":
                continue
            
            if line.startswith("data: "):
                try:
                    chunk_data = json.loads(line[6:])
                    delta = chunk_data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    
                    if content:
                        print_stream(content)
                        full_response += content
                        token_count += 1
                        
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        
        print_stream("\n\n")
    
    return full_response, token_count, time.time() - start_time


def call_llm_with_tools(env, messages, tools=None):
    base_url = env.get("BASE_URL", env.get("LLM_BASE_URL", "")).rstrip("/")
    api_key = env.get("API_KEY", env.get("LLM_API_KEY", ""))
    model = env.get("MODEL", env.get("LLM_MODEL", "gpt-3.5-turbo"))
    
    if not base_url or not api_key:
        raise ValueError("请在 .env 文件中配置 LLM_BASE_URL 和 LLM_API_KEY")
    
    url = f"{base_url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(env.get("LLM_TEMPERATURE", "0.7")),
    }
    
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    timeout = int(env.get("LLM_TIMEOUT", "60"))
    
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"API 请求失败 (HTTP {e.code}): {error_body}")
    except error.URLError as e:
        raise RuntimeError(f"网络连接失败: {e.reason}")


def _convert_bytes(obj):
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='ignore')
    elif isinstance(obj, dict):
        return {k: _convert_bytes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_bytes(item) for item in obj]
    else:
        return obj


def execute_tool_call(tool_call):
    function_name = tool_call["function"]["name"]
    try:
        arguments = json.loads(tool_call["function"]["arguments"])
    except json.JSONDecodeError:
        return {"error": f"参数解析失败: {tool_call['function']['arguments']}"}
    
    func = FUNCTION_MAP.get(function_name)
    if not func:
        return {"error": f"未知工具函数: {function_name}"}
    
    try:
        result = func(**arguments)
        return _convert_bytes(result)
    except Exception as e:
        return {"error": f"执行工具函数失败: {str(e)}"}


def calculate_context_length(messages):
    total_length = 0
    for msg in messages:
        total_length += len(msg.get("content", ""))
    return total_length


def count_real_chat_rounds(messages):
    user_count = 0
    assistant_count = 0
    for msg in messages:
        role = msg.get("role")
        if role == "user":
            user_count += 1
        elif role == "assistant":
            assistant_count += 1
    return min(user_count, assistant_count)


def compress_chat_history(env, messages):
    non_tool_messages = [m for m in messages if m.get("role") != "tool"]
    total_non_tool = len(non_tool_messages)
    split_index = int(total_non_tool * 0.7)
    
    messages_to_compress = non_tool_messages[:split_index]
    messages_to_keep = non_tool_messages[split_index:]
    
    print(f"[系统] 正在自动压缩聊天历史...")
    print(f"[系统] 有效对话消息数: {total_non_tool} (已排除工具调用记录), 压缩前 {split_index} 条，保留后 {len(messages_to_keep)} 条")
    
    old_length = calculate_context_length(messages)
    
    conversation_text = ""
    for msg in messages_to_compress:
        role = "用户" if msg["role"] == "user" else "助手"
        conversation_text += f"{role}: {msg['content']}\n"
    
    summary_user_prompt = f"""请对以下对话历史进行简洁的总结，保留关键信息点。

对话历史：
{conversation_text}

请直接输出总结内容。

总结："""
    
    summary = call_llm_simple(env, [
        {"role": "user", "content": summary_user_prompt}
    ])
    
    summary_message = {
        "role": "user",
        "content": f"【对话历史总结】以上是我们之前的对话内容，请你记住这些信息，接下来继续我们的对话。总结内容：{summary}"
    }
    
    new_messages = [summary_message] + messages_to_keep
    
    new_length = calculate_context_length(new_messages)
    
    print(f"[系统] 压缩完成！原长度: {old_length} 字符，新长度: {new_length} 字符, 压缩率: {(1 - new_length/old_length)*100:.1f}%")
    print(f"[系统] " + "-" * 60)
    
    return new_messages


def check_and_compress(env, messages):
    total_rounds = count_real_chat_rounds(messages)
    context_length = calculate_context_length(messages)
    
    should_compress = False
    reason = ""
    
    if total_rounds > 5:
        should_compress = True
        reason = f"对话轮数超过5轮（当前 {total_rounds} 轮，工具调用记录不计入）"
    
    if context_length > 3000:
        should_compress = True
        reason = f"上下文长度超过3000字符（当前 {context_length} 字符）"
    
    if should_compress:
        print(f"\n[系统] 触发自动总结：{reason}")
        return compress_chat_history(env, messages)
    
    return messages


def extract_key_info(env, messages, last_n_rounds=4):
    non_tool_messages = [m for m in messages if m.get("role") != "tool"]
    recent_messages = non_tool_messages[-last_n_rounds*2:]
    
    conversation_text = ""
    for msg in recent_messages:
        role = "用户" if msg["role"] == "user" else "助手"
        conversation_text += f"{role}: {msg['content']}\n"
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    user_prompt = f"""从对话提取关键信息：

对话：
{conversation_text}

输出：
=== {timestamp} ===
人物：
事件：
时间：
地点：
原因：
==="""
    
    result = call_llm_simple(env, [
        {"role": "user", "content": user_prompt}
    ])
    
    return result


def check_search_intent(env, user_input):
    if user_input.strip().lower().startswith("/search"):
        return True, user_input.replace("/search", "", 1).strip()
    
    prompt = f"""请判断以下用户输入是否明确表达了要搜索、查找、回顾聊天历史或聊天记录的意思：

用户输入：{user_input}

判断规则：
1. 必须明确提到"聊天历史"、"聊天记录"、"历史记录"、"历史对话"才返回 YES
2. 查天气、查资料、问实时信息等，都返回 NO
3. 只是普通问题，返回 NO

如果是，请回答 YES，否则请回答 NO。只输出一个单词。"""
    
    try:
        result = call_llm_simple(env, [{"role": "user", "content": prompt}])
        return result.strip().upper() == "YES", user_input
    except:
        return False, user_input


def check_chained_call_intent(env, user_input):
    if user_input.strip().lower().startswith("/chain"):
        return True, user_input.replace("/chain", "", 1).strip()
    
    keywords = ["链式", "多步", "一步步", "分步", "依次", "逐个", "先", "然后", "接着", "之后", "再", "创建然后", "读取然后"]
    
    user_input_lower = user_input.lower()
    for kw in keywords:
        if kw in user_input_lower:
            return True, user_input
    
    return False, user_input


def signal_handler(signal, frame):
    print("\n\n[系统] 正在退出...")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 60)
    print("Practice 06: 链式工具调用（Chained Tool Calls）")
    print("=" * 60)
    
    try:
        env = load_env()
        print("[OK] 环境配置加载成功")
        print(f"  LLM API: {env.get('BASE_URL', env.get('LLM_BASE_URL'))}")
        print(f"  LLM 模型: {env.get('MODEL', env.get('LLM_MODEL'))}")
        print()
        
        print("[技能系统] 正在加载可用技能列表...")
        skills_result = list_available_skills()
        skills_json_str = json.dumps({"skills": skills_result.get("skills", [])}, ensure_ascii=False, indent=2)
        if skills_result.get("success"):
            print(f"[OK] 发现 {skills_result.get('total', 0)} 个可用技能:")
            for skill in skills_result.get("skills", []):
                print(f"  - [{skill.get('name')}] {skill.get('description')}")
        else:
            print(f"[WARNING] 技能加载失败: {skills_result.get('error')}")
        print()
        
        print("[知识库] 正在连接 AnythingLLM...")
        ws_result = anythingllm_get_workspaces()
        if ws_result.get("success"):
            workspaces = ws_result.get("workspaces", [])
            print(f"[OK] AnythingLLM 连接成功! 发现 {len(workspaces)} 个工作区:")
            for ws in workspaces:
                print(f"  - [{ws.get('slug')}] {ws.get('name')}")
            if env.get("ANYTHINGLLM_WORKSPACE_SLUG"):
                print(f"[OK] 默认工作区: {env.get('ANYTHINGLLM_WORKSPACE_SLUG')}")
        else:
            print(f"[WARNING] AnythingLLM 连接失败: {ws_result.get('error', '未知错误')}")
            print(f"  请确保 AnythingLLM 正在运行: http://localhost:3001")
        print()
        
        ensure_log_file()
        print("[系统] 本地记忆系统已就绪")
        print(f"  日志文件: {LOG_FILE.absolute()}")
        print(f"  文件工作区: {WORKSPACE_ROOT.absolute()}")
        print(f"  技能目录: {SKILLS_ROOT.absolute()}")
        print()
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return
    
    print("[系统] 已整合所有功能：")
    print("  🔗 1. 链式工具调用系统 (多步自动执行)")
    print("  🔌 2. 动态技能加载系统 (自动读取 .agents/skills)")
    print("  📚 3. AnythingLLM 知识库 RAG 检索")
    print("  🧠 4. 聊天历史自动压缩 (5轮/3000字符触发)")
    print("  💾 5. 5W 信息自动提取记忆 (每5轮)")
    print("  🔍 6. 本地聊天历史搜索 (/search + 语义)")
    print("  📁 7. 文件操作系统 (6个工具函数)")
    print("  🕐 8. 时间感知能力 (知道今天几号)")
    print("  🌐 9. 全网数据爬取 (curl_request 访问任意外部网站)")
    print()
    print("[提示] 链式工具调用使用方式：")
    print("  - 直接输入包含「先...然后...接着...」的多步骤请求")
    print("  - 或者使用 /chain 前缀强制触发链式调用: /chain 你的问题")
    print("  - 系统会自动执行多步工具调用，前一步结果作为后一步输入")
    print("  - 示例：先列出当前目录，然后读取第一个文件的内容")
    print()
    
    system_prompt = f"""你是一个全功能智能助手，拥有以下能力：

0. 【链式工具调用能力】
   你拥有多步骤链式工具调用能力，可以根据用户的复杂请求自主规划并执行多步工具调用。

   ⚡ 批量处理工具（处理多文件/多网页时优先使用）：
   - search_files_by_content() - 递归搜索所有包含指定关键词的文件
   - find_files(pattern="*.py") - 按通配符批量查找文件
   - batch_read_files([path1, path2, ...]) - 一次性读取多个文件
   - batch_web_fetch([url1, url2, ...]) - 批量获取多个网页
   - summarize_files_content() - 批量生成文件内容摘要

   链式调用核心规则：
   - ⭐ 处理多个文件/网页时，必须使用批量工具！不要逐个调用！
   - 分析用户请求，判断是否需要多步操作
   - 前一个工具的输出可以作为后一个工具的输入参数
   - 使用 ${{step_N_tool_name_result}} 语法引用前序步骤的结果
   - 例如：${{step_1_search_files_by_content_result}} 引用步骤1结果
   - 例如：${{[f['path'] for f in step_1_result['matching_files']]}} 生成文件路径列表
   - 设置最大迭代次数，防止无限循环
   - 每一步执行后，重新评估是否需要继续调用或可以回答问题

   链式调用示例场景：
   用户问："列出当前目录，找到第一个 .txt 文件并读取其内容"
   执行流程：
   1. 调用 list_directory 获取目录文件列表
   2. 使用步骤1的结果，提取第一个 .txt 文件名
   3. 调用 read_file 读取该文件内容
   4. 任务完成，整合结果回答

   多文件处理真实示例：
   用户问："查找 practice05 下所有含'def'的文件并总结"
   优化执行流程（仅需3步）：
   1. search_files_by_content() → 找出所有匹配文件
   2. batch_read_files() → 一次性读取所有文件
   3. summarize_files_content() → 批量生成摘要
   4. 任务完成！

   上下文变量使用说明：
   - 每一步工具执行的结果都会存储在 context_variables 中
   - 变量名格式: step_序号_工具名_result
   - 后续工具调用的参数可以直接引用这些变量
   - 支持列表推导式、复杂数组索引、字典键访问

1. 【技能系统】
   你拥有动态技能加载能力，可以通过工具加载并执行各种扩展技能。
   可用技能列表（JSON格式）：
   {skills_json_str}

   技能使用指南：
   - 当用户询问有什么技能、可以做什么时，调用 list_available_skills 获取最新技能列表
   - 当判断用户的问题符合某个技能的应用场景时，先调用 load_skill_content 加载技能的详细内容
   - 技能内容加载后，请仔细阅读并严格按照技能的说明执行
   - 加载技能后，请向用户说明正在使用的技能，并遵照技能说明完成任务

2. 【知识库查询能力】
   - anythingllm_list_documents - 列出工作区所有文档文件
   - anythingllm_query - 语义检索知识库内容
   当用户提到"文档仓库"、"文件仓库"、"仓库"、"知识库"、"查文档"时必须调用工具。

3. 【联网获取信息能力】
   - curl_request(url) - 模拟curl访问任意外部网站获取数据
   支持返回完整ANSI艺术字符（如天气图）。
   查询天气、实时信息、最新数据、任何你不知道的信息，都必须调用此工具联网获取。
   
   ⚠️ 【重要天气提示】
   wttr.in 只支持县级以上城市，乡镇/景区可能没有数据：
   - 查"青城山"请用"都江堰"替代
   - 小地方查不到就用附近的大城市，并向用户说明
   - 如果返回内容为空，就是城市名不被支持，换大城市重试
   
   常用网址示例：
   - 天气ASCII艺术图: https://wttr.in/成都
   - 天气JSON数据: https://wttr.in/都江堰?format=j1
   - 任何API或网页都可以访问

4. 【时间感知能力】
   - get_current_datetime() - 获取当前系统日期和时间
   ⚠️ 【重要强制规则】
   当用户询问今天几号、现在几点、星期几、当前时间，或者任何需要知道当前日期时间才能回答的问题，**必须调用此工具**！
   禁止凭空猜测时间，必须调用工具获取真实数据。

5. 【文件操作能力】
   - list_directory / rename_file / delete_file
   - create_file / read_file
   所有文件操作都在 {WORKSPACE_ROOT.absolute()} 目录下进行。

重要指令：
1. 凡是需要获取实时信息、外部数据、最新天气的，**必须调用 curl_request 联网获取**，不要凭空回答
2. 凡是需要获取知识库信息的，必须先调用工具获取真实数据
3. 凡是需要知道当前日期时间的，**必须调用 get_current_datetime**，禁止凭空回答
4. 凡是需要使用技能的，先调用 load_skill_content 加载技能详细说明再执行
5. 必须严格按照工具函数的参数格式调用
6. 执行工具后，用自然语言向用户总结执行结果
"""
    
    messages = [
        {"role": "user", "content": system_prompt},
        {"role": "assistant", "content": "好的，我已了解所有功能。我会在需要时正确调用工具函数，包括链式多步工具调用。"}
    ]
    
    chat_count = 0
    
    print("-" * 60)
    print("[系统] 开始对话！输入问题开始使用工具，按 Ctrl+C 退出")
    print()
    
    while True:
        try:
            user_input = input("[你] ")
            
            if not user_input.strip():
                continue
            
            is_chained, chained_query = check_chained_call_intent(env, user_input)
            
            if is_chained:
                print(f"\n[系统] 触发链式工具调用模式")
                print(f"  请求: {chained_query if chained_query else user_input}")
                
                chain_result = execute_chained_tool_call(
                    env, 
                    chained_query if chained_query else user_input,
                    max_iterations=10
                )
                
                if chain_result.get("is_completed"):
                    print_stream("\n[AI] ")
                    print_stream(chain_result.get("final_answer", ""))
                    print_stream("\n\n")
                    final_answer = chain_result.get("final_answer", "")
                else:
                    print_stream("\n[AI] ")
                    print_stream(f"链式调用执行过程中出现问题: {chain_result.get('error', '未知错误')}")
                    print_stream("\n\n")
                    final_answer = f"链式调用执行失败: {chain_result.get('error', '未知错误')}"
                
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": final_answer})
                chat_count += 1
                
                if chat_count % 5 == 0:
                    print(f"\n[系统] 触发自动记忆提取...")
                    key_info = extract_key_info(env, messages)
                    append_to_log(key_info)
                    print(f"  关键信息已提取并写入日志")
                
                messages = check_and_compress(env, messages)
                continue
            
            is_search, query = check_search_intent(env, user_input)
            
            if is_search:
                search_messages = search_chat_history(env, query)
                print(f"\n[系统] 本地聊天记忆检索")
                print(f"  检索关键词: {query if query else '全部历史'}")
                print()
                final_answer, tokens, elapsed = call_llm_final_answer_stream(env, search_messages)
                
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": final_answer})
                chat_count += 1
                continue
            
            messages.append({"role": "user", "content": user_input})
            
            while True:
                response = call_llm_with_tools(env, messages, TOOLS)
                response_message = response["choices"][0]["message"]
                
                messages.append(response_message)
                
                if "tool_calls" not in response_message or not response_message["tool_calls"]:
                    break
                
                print()
                for tool_call in response_message["tool_calls"]:
                    function_name = tool_call["function"]["name"]
                    print(f"[调用工具] {function_name}")
                    
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                        for k, v in arguments.items():
                            print(f"  参数 {k}: {v}")
                    except:
                        pass
                    
                    tool_result = execute_tool_call(tool_call)
                    
                    print(f"[执行结果] {json.dumps(tool_result, ensure_ascii=False)[:200]}...")
                    print()
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
            
            final_answer, tokens, elapsed = call_llm_final_answer_stream(env, messages)
            chat_count += 1
            
            if chat_count % 5 == 0:
                print(f"\n[系统] 触发自动记忆提取...")
                key_info = extract_key_info(env, messages)
                append_to_log(key_info)
                print(f"  关键信息已提取并写入日志")
            
            messages = check_and_compress(env, messages)
            
        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()
            print()


if __name__ == "__main__":
    main()
