import json
import time
import signal
import sys
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


def print_stream(content):
    sys.stdout.write(content)
    sys.stdout.flush()


def call_llm_stream(env, messages):
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
    
    start_time = time.time()
    full_response = ""
    token_count = 0
    
    try:
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
            
    except error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"API 请求失败 (HTTP {e.code}): {error_body}")
    except error.URLError as e:
        raise RuntimeError(f"网络连接失败: {e.reason}")
    
    elapsed_time = time.time() - start_time
    tokens_per_second = token_count / elapsed_time if elapsed_time > 0 else 0
    
    stats = {
        "response_tokens": token_count,
        "elapsed_time": elapsed_time,
        "tokens_per_second": tokens_per_second
    }
    
    return full_response, stats


def signal_handler(sig, frame):
    print("\n\n")
    print("=" * 60)
    print("[系统] 对话已结束，再见！")
    print("=" * 60)
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 60)
    print("Practice 02: 流式对话客户端")
    print("=" * 60)
    
    try:
        env = load_env()
        print(f"[OK] 环境配置加载成功")
        print(f"  API: {env.get('LLM_BASE_URL')}")
        print(f"  模型: {env.get('LLM_MODEL')}")
        print()
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return
    
    print("[系统] 欢迎！输入内容开始聊天，按 Ctrl+C 退出")
    print("-" * 60)
    print()
    
    messages = []
    
    while True:
        try:
            user_input = input("[你] ")
            
            if not user_input.strip():
                continue
            
            messages.append({"role": "user", "content": user_input})
            
            try:
                response, stats = call_llm_stream(env, messages)
                
                messages.append({"role": "assistant", "content": response})
                
                print(f"  ─── 本次对话统计 ───")
                print(f"  历史消息数: {len(messages) // 2} 轮")
                print(f"  输出 tokens: {stats['response_tokens']}")
                print(f"  耗时: {stats['elapsed_time']:.2f} 秒")
                print(f"  生成速度: {stats['tokens_per_second']:.2f} tokens/秒")
                print()
                print("-" * 60)
                print()
                
            except Exception as e:
                print(f"\n[ERROR] 调用失败: {e}")
                print()
                messages.pop()
                
        except EOFError:
            signal_handler(None, None)


if __name__ == "__main__":
    main()
