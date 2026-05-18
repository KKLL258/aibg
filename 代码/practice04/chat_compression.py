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
        "temperature": float(env.get("LLM_TEMPERATURE", "0.7")),
        "stream": stream,
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
    
    with request.urlopen(req, timeout=timeout) as response:
        response_data = json.loads(response.read().decode("utf-8"))
        return response_data["choices"][0]["message"]["content"]


def call_llm_stream(env, messages):
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
    
    summary_system_prompt = "你是一个对话总结专家。请对用户提供的对话历史进行简洁的总结，保留所有关键信息、事实和约定，不要遗漏重要的上下文。"
    
    summary_user_prompt = f"""请对以下对话历史进行简洁的总结，保留关键信息点。

对话历史：
{conversation_text}

请直接输出总结内容，开头不需要加【对话历史总结】标记。

总结："""
    
    summary = call_llm_simple(env, [
        {"role": "system", "content": summary_system_prompt},
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


def signal_handler(sig, frame):
    print("\n\n")
    print("=" * 60)
    print("[系统] 对话已结束，再见！")
    print("=" * 60)
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 60)
    print("Practice 03: 聊天历史自动总结压缩")
    print("=" * 60)
    
    try:
        env = load_env()
        print(f"[OK] 环境配置加载成功")
        print(f"  API: {env.get('BASE_URL', env.get('LLM_BASE_URL', '未配置'))}")
        print(f"  模型: {env.get('MODEL', env.get('LLM_MODEL', '未配置'))}")
        print()
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return
    
    print("[系统] 欢迎！输入内容开始聊天，按 Ctrl+C 退出")
    print("[系统] 超过5轮对话或上下文长度超过3000字符将自动触发总结压缩")
    print("-" * 60)
    print()
    
    messages = []
    
    while True:
        try:
            user_input = input("[你] ")
            
            if not user_input.strip():
                continue
            
            messages.append({"role": "user", "content": user_input})
            
            messages = check_and_compress(env, messages)
            
            try:
                response, stats = call_llm_stream(env, messages)
                
                messages.append({"role": "assistant", "content": response})
                
                print(f"  ─── 本次对话统计 ───")
                print(f"  历史消息数: {len(messages) // 2} 轮")
                print(f"  上下文长度: {calculate_context_length(messages)} 字符")
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
