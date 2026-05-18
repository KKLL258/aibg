import os
import sys
import json
import time
import signal
import threading
import subprocess
from urllib import request, error
from pathlib import Path


LOG_FILE = Path(__file__).parent / "chat-log" / "log.txt"
WORKSPACE_ROOT = Path(__file__).parent / "workspace"
WORKSPACE_ROOT.mkdir(exist_ok=True)


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
    """模拟 curl 访问网页，返回网页内容
    
    【常用示例】
    - 天气图: curl_request("https://wttr.in/成都")
    - 天气JSON: curl_request("https://wttr.in/青城山?format=j1")
    
    Args:
        url: 要访问的网页 URL（必须以 http:// 或 https:// 开头）
        method: HTTP 方法，支持 GET/POST
        timeout: 超时时间（秒），默认 30 秒
    """
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
    "read_file": read_file,
    "get_current_datetime": get_current_datetime,
    "curl_request": curl_request
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
    
    if not stream:
        with request.urlopen(req, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            return response_data["choices"][0]["message"]["content"]
    else:
        full_response = ""
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


def compress_chat_history(env, messages):
    total_messages = len(messages)
    split_index = int(total_messages * 0.7)
    
    messages_to_compress = messages[:split_index]
    messages_to_keep = messages[split_index:]
    
    print(f"[系统] 正在自动压缩聊天历史...")
    print(f"[系统] 总消息数: {total_messages}, 压缩前 {split_index} 条，保留后 {len(messages_to_keep)} 条")
    
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
    total_rounds = len(messages) // 2
    context_length = calculate_context_length(messages)
    
    should_compress = False
    reason = ""
    
    if total_rounds > 5:
        should_compress = True
        reason = f"对话轮数超过5轮（当前 {total_rounds} 轮）"
    
    if context_length > 3000:
        should_compress = True
        reason = f"上下文长度超过3000字符（当前 {context_length} 字符）"
    
    if should_compress:
        print(f"\n[系统] 触发自动总结：{reason}")
        return compress_chat_history(env, messages)
    
    return messages


def extract_key_info(env, messages, last_n_rounds=4):
    recent_messages = messages[-last_n_rounds*2:]
    
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


def signal_handler(signal, frame):
    print("\n\n[系统] 正在退出...")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 60)
    print("Practice 04: 终极全功能 Agent - 完整整合版")
    print("=" * 60)
    
    try:
        env = load_env()
        print("[OK] 环境配置加载成功")
        print(f"  LLM API: {env.get('BASE_URL', env.get('LLM_BASE_URL'))}")
        print(f"  LLM 模型: {env.get('MODEL', env.get('LLM_MODEL'))}")
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
        print()
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return
    
    print("[系统] 已整合所有功能：")
    print("  📚 1. AnythingLLM 知识库 RAG 检索")
    print("  🧠 2. 聊天历史自动压缩 (5轮/3000字符触发)")
    print("  💾 3. 5W 信息自动提取记忆 (每5轮)")
    print("  🔍 4. 本地聊天历史搜索 (/search + 语义)")
    print("  📁 5. 文件操作系统 (6个工具函数)")
    print("  🕐 6. 时间感知能力 (知道今天几号)")
    print("  🌐 7. 全网数据爬取 (curl_request 访问任意外部网站)")
    print()
    print("[提示] 触发知识库关键词：")
    print("  「列出文件」、「仓库有什么」、「文档仓库」")
    print("  「文件仓库」、「知识库」、「查文档」")
    print()
    print("[提示] 触发本地记忆搜索：")
    print("  /search + 关键词，或直接说「查找聊天历史」")
    print()
    
    system_prompt = f"""你是一个全功能智能助手，拥有以下能力：

1. 【知识库查询能力】
   - anythingllm_list_documents - 列出工作区所有文档文件
   - anythingllm_query - 语义检索知识库内容
   当用户提到"文档仓库"、"文件仓库"、"仓库"、"知识库"、"查文档"时必须调用工具。

2. 【联网获取信息能力】
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

3. 【文件操作能力】
   - list_directory / rename_file / delete_file
   - create_file / read_file
   所有文件操作都在 {WORKSPACE_ROOT.absolute()} 目录下进行。

重要指令：
1. 凡是需要获取实时信息、外部数据、最新天气的，**必须调用 curl_request 联网获取**，不要凭空回答
2. 凡是需要获取知识库信息的，必须先调用工具获取真实数据
3. 必须严格按照工具函数的参数格式调用
4. 执行工具后，用自然语言向用户总结执行结果
"""
    
    messages = [
        {"role": "user", "content": system_prompt},
        {"role": "assistant", "content": "好的，我已了解所有功能。我会在需要时正确调用工具函数。"}
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
            
            is_search, query = check_search_intent(env, user_input)
            
            if is_search:
                search_messages = search_chat_history(env, query)
                print(f"\n[系统] 本地聊天记忆检索")
                print(f"  检索关键词: {query if query else '全部历史'}")
                print()
                final_answer, tokens, elapsed = call_llm_final_answer_stream(env, search_messages)
                print("-" * 60)
                continue
            
            messages.append({"role": "user", "content": user_input})
            
            messages = check_and_compress(env, messages)
            
            max_tool_calls = 15
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
                print(f"\n[已达到最大工具调用次数 ({max_tool_calls} 次)]")
            
            final_answer, tokens, elapsed = call_llm_final_answer_stream(env, messages)
            messages.append({"role": "assistant", "content": final_answer})
            chat_count += 1
            
            if chat_count % 5 == 0:
                print(f"[系统] 后台提取关键信息中...")
                
                def background_extract():
                    try:
                        key_info = extract_key_info(env, messages.copy(), 4)
                        append_to_log(key_info)
                        print(f"\n[系统] ✓ 5W记忆已更新至日志文件")
                        print(key_info)
                        print(f"[你] ", end="", flush=True)
                    except Exception as e:
                        print(f"\n[系统] 提取跳过 ({str(e)[:30]})")
                        print(f"[你] ", end="", flush=True)
                
                threading.Thread(target=background_extract, daemon=True).start()
            
            print(f"  ─── 本次对话统计 ───")
            print(f"  当前轮次: 第 {chat_count} 轮")
            print(f"  历史消息数: {len(messages) // 2} 轮")
            print(f"  上下文长度: {calculate_context_length(messages)} 字符")
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n[系统] 再见！")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}\n")


if __name__ == "__main__":
    main()
