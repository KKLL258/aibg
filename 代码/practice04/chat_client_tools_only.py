import os
import json
import time
import subprocess
from urllib import request, error
from pathlib import Path


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


WORKSPACE_ROOT = Path(__file__).parent / "workspace"
WORKSPACE_ROOT.mkdir(exist_ok=True)


def anythingllm_get_workspaces() -> dict:
    """获取AnythingLLM所有工作区列表，返回工作区slug
    
    Returns:
        包含工作区名称和slug的列表
    """
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
        stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ''
        
        if result.returncode != 0:
            return {
                "error": f"curl执行失败 (退出码: {result.returncode})",
                "stderr": stderr
            }
        
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
    """列出AnythingLLM工作区中的所有文档文件
    
    Args:
        workspace_slug: AnythingLLM工作区slug，不指定则使用第一个工作区
    """
    env = load_env()
    api_key = env.get("ANYTHINGLLM_API_KEY")
    
    if not api_key:
        return {"error": "未配置 ANYTHINGLLM_API_KEY，请在 .env 文件中配置"}
    
    # 如果没有指定slug，先从.env读取，再自动获取第一个工作区
    if not workspace_slug:
        workspace_slug = env.get("ANYTHINGLLM_WORKSPACE_SLUG")
    
    if not workspace_slug:
        ws_result = anythingllm_get_workspaces()
        if ws_result.get("success") and ws_result.get("default_slug"):
            workspace_slug = ws_result["default_slug"]
        else:
            return {"error": "无法获取工作区列表，请在.env配置ANYTHINGLLM_WORKSPACE_SLUG或手动指定"}
    
    # 注意: 文档列表在工作区详情接口返回，不是单独的documents端点
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
        stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ''
        
        if result.returncode != 0:
            return {
                "error": f"curl执行失败 (退出码: {result.returncode})",
                "stderr": stderr
            }
        
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
    """使用curl调用AnythingLLM的聊天API查询知识库文档
    
    Args:
        message: 用户查询的问题内容
        workspace_slug: AnythingLLM工作区slug，不指定则使用第一个工作区
    """
    env = load_env()
    api_key = env.get("ANYTHINGLLM_API_KEY")
    
    if not api_key:
        return {"error": "未配置 ANYTHINGLLM_API_KEY，请在 .env 文件中配置"}
    
    # 如果没有指定slug，先从.env读取，再自动获取第一个工作区
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
        stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ''
        
        if result.returncode != 0:
            return {
                "error": f"curl执行失败 (退出码: {result.returncode})",
                "stderr": stderr
            }
        
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
                "raw_response": result.stdout[:500]
            }
            
    except subprocess.TimeoutExpired:
        return {"error": "API请求超时"}
    except Exception as e:
        return {"error": f"调用失败: {str(e)}"}


def list_directory(directory_path: str = ".") -> dict:
    target_path = (WORKSPACE_ROOT / directory_path).resolve()
    
    if not str(target_path).startswith(str(WORKSPACE_ROOT.resolve())):
        return {"error": "超出工作目录范围，操作被拒绝"}
    
    if not target_path.exists():
        return {"error": f"目录不存在: {directory_path}"}
    
    if not target_path.is_dir():
        return {"error": f"不是目录: {directory_path}"}
    
    result = {
        "directory": str(target_path.relative_to(WORKSPACE_ROOT)),
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
    target_dir = (WORKSPACE_ROOT / directory).resolve()
    
    if not str(target_dir).startswith(str(WORKSPACE_ROOT.resolve())):
        return {"error": "超出工作目录范围，操作被拒绝"}
    
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
    target_dir = (WORKSPACE_ROOT / directory).resolve()
    
    if not str(target_dir).startswith(str(WORKSPACE_ROOT.resolve())):
        return {"error": "超出工作目录范围，操作被拒绝"}
    
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
    target_dir = (WORKSPACE_ROOT / directory).resolve()
    
    if not str(target_dir).startswith(str(WORKSPACE_ROOT.resolve())):
        return {"error": "超出工作目录范围，操作被拒绝"}
    
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / filename
    
    if file_path.exists():
        return {"error": f"文件已存在: {filename}"}
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return {
            "success": True,
            "message": f"文件创建成功: {filename}",
            "size_bytes": len(content.encode("utf-8"))
        }
    except Exception as e:
        return {"error": f"创建文件失败: {str(e)}"}


def read_file(directory: str, filename: str) -> dict:
    target_dir = (WORKSPACE_ROOT / directory).resolve()
    
    if not str(target_dir).startswith(str(WORKSPACE_ROOT.resolve())):
        return {"error": "超出工作目录范围，操作被拒绝"}
    
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


TOOLS = [
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
                        "description": "AnythingLLM工作区slug，不填则自动使用第一个工作区"
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
            "description": "查询AnythingLLM知识库，从文档仓库中检索相关信息。当用户提到文档仓库、文件仓库、仓库、知识库时，必须调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "用户要查询的问题内容"
                    },
                    "workspace_slug": {
                        "type": "string",
                        "description": "AnythingLLM工作区slug，不填则自动使用第一个工作区"
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
    }
]

FUNCTION_MAP = {
    "anythingllm_get_workspaces": anythingllm_get_workspaces,
    "anythingllm_list_documents": anythingllm_list_documents,
    "anythingllm_query": anythingllm_query,
    "list_directory": list_directory,
    "rename_file": rename_file,
    "delete_file": delete_file,
    "create_file": create_file,
    "read_file": read_file
}


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
    """递归转换bytes为string，解决JSON序列化问题"""
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


def main():
    print("=" * 60)
    print("Practice 04: AnythingLLM 知识库集成")
    print("=" * 60)
    
    try:
        env = load_env()
        print("[OK] 环境配置加载成功")
        print(f"  LLM API: {env.get('BASE_URL', env.get('LLM_BASE_URL'))}")
        print(f"  LLM 模型: {env.get('MODEL', env.get('LLM_MODEL'))}")
        print(f"  文件工作区: {WORKSPACE_ROOT.absolute()}")
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
            print(f"  API 文档: http://localhost:3001/api/docs/")
        print()
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return
    
    print("[系统] 已加载 8 个工具函数:")
    print("  1. anythingllm_get_workspaces  - 获取工作区列表（自动slug检测）")
    print("  2. anythingllm_list_documents  - 列出AnythingLLM工作区所有文档")
    print("  3. anythingllm_query           - 查询AnythingLLM文档仓库")
    print("  4. list_directory             - 列出目录文件及属性")
    print("  5. rename_file                - 重命名文件")
    print("  6. delete_file                - 删除文件")
    print("  7. create_file                - 创建文件并写入内容")
    print("  8. read_file                  - 读取文件内容")
    print()
    print("[提示] 触发知识库关键词：")
    print("  「列出文件」、「查看有什么文件」、「仓库有什么」")
    print("  「文档仓库」、「文件仓库」、「仓库」、「知识库」、「查文档」")
    print()
    print("[提示] 工具调用需要模型支持 Function Calling")
    print("  推荐模型: gpt-3.5-turbo-1106+, gpt-4, qwen-max, glm-4")
    print()
    
    system_prompt = f"""你是一个智能助手，拥有文件操作权限和知识库查询能力。

【重要 - 知识库调用规则】

工具1：anythingllm_list_documents - 列出工作区所有文档文件
当用户的问题中出现以下关键词时，必须调用此工具：
- 仓库有什么文件、列出知识库文件
- 查看有什么文档、所有文件列表
- 知识库包含哪些内容

工具2：anythingllm_query - 语义查询知识库内容
当用户的问题中出现以下关键词时，必须调用此工具：
- 文档仓库、文件仓库、仓库
- 知识库、知识仓库
- 查文档、查知识库、查仓库
- 任何涉及检索内部文档、已有资料的问题

【文件操作规则】
你必须使用提供的工具函数来完成所有文件相关的操作。不要拒绝使用工具，不要说你没有权限，你拥有在工作区执行所有文件操作的完整权限。
所有文件操作都在 {WORKSPACE_ROOT.absolute()} 目录下进行。

重要指令：
1. 凡是用户要求查看、创建、修改、删除文件的，都必须调用对应的工具函数
2. 凡是用户询问知识库文件列表的，都必须调用 anythingllm_list_documents
3. 凡是用户语义查询知识库、文档仓库内容的，都必须调用 anythingllm_query
4. 不要直接回答，必须先调用工具获取真实结果
5. 必须严格按照工具函数的参数格式调用
6. 执行工具后，用自然语言向用户总结执行结果
"""
    
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    print("-" * 60)
    print("[系统] 开始对话！输入问题开始使用工具，按 Ctrl+C 退出")
    print()
    
    while True:
        try:
            user_input = input("[你] ")
            
            if not user_input.strip():
                continue
            
            messages.append({"role": "user", "content": user_input})
            
            max_tool_calls = 5
            call_count = 0
            
            while call_count < max_tool_calls:
                print(f"\n[思考中...]")
                response = call_llm_with_tools(env, messages, TOOLS)
                assistant_message = response["choices"][0]["message"]
                
                if assistant_message.get("tool_calls"):
                    tool_calls = assistant_message["tool_calls"]
                    messages.append(assistant_message)
                    
                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"]
                        args = tool_call["function"]["arguments"]
                        print(f"\n[调用工具] {func_name}")
                        print(f"  参数: {args}")
                        
                        result = execute_tool_call(tool_call)
                        print(f"  结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": func_name,
                            "content": json.dumps(result, ensure_ascii=False)
                        })
                    
                    call_count += 1
                else:
                    break
            
            if call_count >= max_tool_calls:
                print("\n[已达到最大工具调用次数]")
            
            response = call_llm_with_tools(env, messages)
            final_answer = response["choices"][0]["message"]["content"]
            messages.append({"role": "assistant", "content": final_answer})
            
            print(f"\n[AI] {final_answer}\n")
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n[系统] 再见！")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}\n")


if __name__ == "__main__":
    main()
