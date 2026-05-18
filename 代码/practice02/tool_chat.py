import os
import json
import time
import re
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


def curl_request(url: str, method: str = "GET", timeout: int = 30) -> dict:
    """模拟 curl 访问网页，返回网页内容
    
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


TOOL_FUNCTIONS = {
    "list_directory": list_directory,
    "rename_file": rename_file,
    "delete_file": delete_file,
    "create_file": create_file,
    "read_file": read_file,
    "curl_request": curl_request
}


def build_system_prompt():
    """构建系统提示词，每次调用动态更新日期"""
    today = time.strftime("%Y年%m月%d日 %H:%M:%S 星期%w", time.localtime())
    weekday_map = {"0": "日", "1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六"}
    today = today.replace("星期" + today[-1], "星期" + weekday_map[today[-1]])
    
    return f"""你是一个智能助手，可以通过调用工具来操作系统文件和访问网络。

当前系统时间: {today}
工作区目录: {WORKSPACE_ROOT.absolute()}

你拥有以下6个工具可以调用：

【工具1】list_directory - 列出目录下的文件
参数：
  - directory_path: 目录路径，可选，默认为 "."

【工具2】rename_file - 重命名文件
参数：
  - directory: 文件所在目录
  - old_name: 原文件名
  - new_name: 新文件名

【工具3】delete_file - 删除文件
参数：
  - directory: 文件所在目录
  - filename: 要删除的文件名

【工具4】create_file - 创建文件并写入内容
参数：
  - directory: 目标目录
  - filename: 文件名
  - content: 文件内容，可选

【工具5】read_file - 读取文件内容
参数：
  - directory: 文件所在目录
  - filename: 要读取的文件名

【工具6】curl_request - 模拟 curl 访问网页，获取网页内容
参数：
  - url: 要访问的网页完整 URL（必须以 http:// 或 https:// 开头）
  - method: HTTP 方法，可选，支持 GET/POST，默认为 GET
  - timeout: 超时时间，可选，单位秒，默认为 30
说明：
  - 纯文本内容最大返回 20000 字符，支持完整的 ANSI 艺术（如 wttr.in 天气图）
  - 返回结果包含 truncated 字段，表示内容是否被截断

==== 重要调用规则 ====
1. 当需要执行文件操作或网络请求时，请输出严格的JSON格式来调用工具
2. 工具调用格式：
   ```json
   {{"name": "工具名", "parameters": {{"参数名": "参数值"}}}}
   ```
3. 每次只能调用一个工具
4. 工具执行后我会给你结果，然后你再总结回答
5. 不要说你"没有权限"，你可以自由调用这些工具
6. 如果不需要调用工具，请直接用自然语言回答用户
7. 调用 curl_request 时，请总结返回的网页内容，不要直接输出完整 HTML
"""


def call_llm(env, messages):
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
    
    if "LLM_MAX_TOKENS" in env:
        payload["max_tokens"] = int(env["LLM_MAX_TOKENS"])
    
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


def parse_tool_call(content):
    pattern = r'```json\s*(\{.*?\})\s*```'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        try:
            tool_call = json.loads(match.group(1))
            return tool_call
        except json.JSONDecodeError:
            return None
    
    try:
        tool_call = json.loads(content)
        if "name" in tool_call:
            return tool_call
    except:
        pass
    
    return None


def execute_tool(tool_call):
    name = tool_call.get("name")
    parameters = tool_call.get("parameters", {})
    
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return {"error": f"未知工具: {name}"}
    
    try:
        result = func(**parameters)
        return result
    except Exception as e:
        return {"error": f"执行失败: {str(e)}"}


def main():
    print("=" * 60)
    print("Practice 02: 系统提示词驱动工具调用")
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
    
    print("[系统] 已加载 6 个工具函数:")
    print("  1. list_directory  - 列出目录文件及属性")
    print("  2. rename_file     - 重命名文件")
    print("  3. delete_file     - 删除文件")
    print("  4. create_file     - 创建文件并写入内容")
    print("  5. read_file       - 读取文件内容")
    print("  6. curl_request    - 模拟 curl 访问网页")
    print()
    print("[原理] 通过系统提示词+JSON解析实现工具调用")
    print()
    print("-" * 60)
    print("[系统] 开始对话！输入问题开始使用工具，按 Ctrl+C 退出")
    print()
    
    messages = []
    
    while True:
        try:
            user_input = input("[你] ")
            
            if not user_input.strip():
                continue
            
            messages.append({"role": "user", "content": user_input})
            
            max_tool_calls = 10
            call_count = 0
            
            while call_count < max_tool_calls:
                print(f"\n[思考中...]")
                
                messages_with_system = [{"role": "system", "content": build_system_prompt()}] + messages
                
                response = call_llm(env, messages_with_system)
                content = response["choices"][0]["message"]["content"]
                
                tool_call = parse_tool_call(content)
                
                if tool_call:
                    name = tool_call.get("name")
                    params = tool_call.get("parameters", {})
                    print(f"\n[调用工具] {name}")
                    print(f"  参数: {json.dumps(params, ensure_ascii=False)}")
                    
                    result = execute_tool(tool_call)
                    print(f"  结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": f"工具执行结果：{json.dumps(result, ensure_ascii=False)}。请基于这个结果继续处理，如果还需要调用其他工具请继续输出JSON，不需要的话就直接总结结果回答我。"
                    })
                    
                    call_count += 1
                else:
                    print(f"\n[AI] {content}\n")
                    messages.append({"role": "assistant", "content": content})
                    break
            
            if call_count >= max_tool_calls:
                print("\n[已达到最大工具调用次数，正在总结结果...]")
                messages_with_system = [{"role": "system", "content": build_system_prompt()}] + messages
                response = call_llm(env, messages_with_system)
                final_answer = response["choices"][0]["message"]["content"]
                print(f"\n[AI] {final_answer}\n")
                messages.append({"role": "assistant", "content": final_answer})
            
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n[系统] 再见！")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}\n")


if __name__ == "__main__":
    main()
