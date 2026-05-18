import os
import json
import time
from urllib import request, error
from pathlib import Path


def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"请先将 env.example 复制为 {env_path} 并填写配置")
    
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


def list_directory(directory_path: str = ".") -> dict:
    """列出指定目录下的所有文件和子目录，包含文件基本属性
    
    Args:
        directory_path: 要列出的目录路径（相对于 workspace 根目录）
    """
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
    """修改目录下某个文件的名称
    
    Args:
        directory: 文件所在目录（相对于 workspace 根目录）
        old_name: 原文件名
        new_name: 新文件名
    """
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
    """删除目录下的某个文件
    
    Args:
        directory: 文件所在目录（相对于 workspace 根目录）
        filename: 要删除的文件名
    """
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
    """在指定目录下新建文件并写入内容
    
    Args:
        directory: 目标目录（相对于 workspace 根目录）
        filename: 要创建的文件名
        content: 要写入的文件内容
    """
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
    """读取指定目录下某个文件的内容
    
    Args:
        directory: 文件所在目录（相对于 workspace 根目录）
        filename: 要读取的文件名
    """
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
    "list_directory": list_directory,
    "rename_file": rename_file,
    "delete_file": delete_file,
    "create_file": create_file,
    "read_file": read_file
}


def call_llm_with_tools(env, messages, tools=None):
    base_url = env.get("LLM_BASE_URL", "").rstrip("/")
    api_key = env.get("LLM_API_KEY", "")
    model = env.get("LLM_MODEL", "gpt-3.5-turbo")
    
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


def execute_tool_call(tool_call):
    function_name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])
    
    func = FUNCTION_MAP.get(function_name)
    if not func:
        return {"error": f"未知工具函数: {function_name}"}
    
    try:
        result = func(**arguments)
        return result
    except Exception as e:
        return {"error": f"执行工具函数失败: {str(e)}"}


def main():
    print("=" * 60)
    print("Practice 03: 工具调用 Function Calling")
    print("=" * 60)
    
    try:
        env = load_env()
        print("[OK] 环境配置加载成功")
        print(f"  API: {env.get('LLM_BASE_URL')}")
        print(f"  模型: {env.get('LLM_MODEL')}")
        print(f"  工作区: {WORKSPACE_ROOT.absolute()}")
        print()
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return
    
    print("[系统] 已加载 5 个文件操作工具:")
    print("  1. list_directory  - 列出目录文件及属性")
    print("  2. rename_file     - 重命名文件")
    print("  3. delete_file     - 删除文件")
    print("  4. create_file     - 创建文件并写入内容")
    print("  5. read_file       - 读取文件内容")
    print()
    print("[提示] 工具调用需要模型支持 Function Calling")
    print("  推荐模型: gpt-3.5-turbo-1106+, gpt-4, qwen-max, glm-4")
    print("  如果模型不支持工具调用，会直接回复而不使用工具")
    print()
    
    messages = [
        {"role": "system", "content": f"你是一个拥有文件操作权限的智能助手。你必须使用提供的工具函数来完成所有文件相关的操作。不要拒绝使用工具，不要说你没有权限，你拥有在工作区执行所有文件操作的完整权限。\n\n所有文件操作都在 {WORKSPACE_ROOT.absolute()} 目录下进行。\n\n重要指令：\n1. 凡是用户要求查看、创建、修改、删除文件的，都必须调用对应的工具函数\n2. 不要直接回答，必须先调用工具获取真实结果\n3. 必须严格按照工具函数的参数格式调用\n4. 执行工具后，用自然语言向用户总结执行结果"}
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
                    if assistant_message.get("content"):
                        print(f"\n[模型回复] {assistant_message['content']}")
                    print("\n[未调用工具，直接回复]")
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
