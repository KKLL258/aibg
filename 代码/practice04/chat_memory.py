import json
import time
import signal
import sys
import threading
from urllib import request, error
from pathlib import Path


LOG_FILE = Path(__file__).parent / "chat-log" / "log.txt"


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
    
    timeout = int(env.get("LLM_TIMEOUT", "300"))
    
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


def extract_key_info(env, messages, last_n_rounds=5):
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
    
    prompt = f"""请判断以下用户输入是否表达了要搜索、查找、回顾聊天历史或记录的意思：
用户输入：{user_input}

如果是，请回答 YES，否则请回答 NO。只输出一个单词。"""
    
    try:
        result = call_llm_simple(env, [{"role": "user", "content": prompt}])
        return result.strip().upper() == "YES", user_input
    except:
        return False, user_input


def search_chat_history(env, query):
    print(f"[系统] 正在检索聊天历史记录...")
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


def signal_handler(sig, frame):
    print("\n\n")
    print("=" * 60)
    print("[系统] 对话已结束，再见！")
    print(f"[系统] 聊天记录已保存至: {LOG_FILE}")
    print("=" * 60)
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 60)
    print("Practice 03: 聊天记忆系统 + 5W信息提取")
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
    
    ensure_log_file()
    
    print("[系统] 欢迎！输入内容开始聊天，按 Ctrl+C 退出")
    print("[系统] 功能1: 每5轮对话自动提取5W关键信息至本地记忆库")
    print("[系统] 功能2: /search 关键词 或直接说'查找聊天历史'")
    print(f"[系统] 输出Token: {env.get('LLM_MAX_TOKENS', 2000)} | 搜索自动截断: 8000 字符")
    print(f"[系统] 日志文件: {LOG_FILE}")
    print("-" * 60)
    print()
    
    messages = []
    chat_count = 0
    
    while True:
        try:
            user_input = input("[你] ")
            
            if not user_input.strip():
                continue
            
            is_search, query = check_search_intent(env, user_input)
            
            if is_search:
                try:
                    search_messages = search_chat_history(env, query)
                    response, stats = call_llm_stream(env, search_messages)
                    
                    print(f"  ─── 历史检索结果 ───")
                    print(f"  检索关键词: {query if query else '全部历史'}")
                    print(f"  输出 tokens: {stats['response_tokens']}")
                    print()
                    print("-" * 60)
                    print()
                except Exception as e:
                    print(f"\n[ERROR] 检索失败: {e}")
                    print()
                    print("-" * 60)
                    print()
                continue
            
            messages.append({"role": "user", "content": user_input})
            
            messages = check_and_compress(env, messages)
            
            try:
                response, stats = call_llm_stream(env, messages)
                
                messages.append({"role": "assistant", "content": response})
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
                print(f"  输出 tokens: {stats['response_tokens']}")
                print(f"  耗时: {stats['elapsed_time']:.2f} 秒")
                print(f"  生成速度: {stats['tokens_per_second']:.2f} tokens/秒")
                print()
                print("-" * 60)
                print()
                
            except Exception as e:
                print(f"\n[ERROR] 调用失败: {e}")
                print()
                if len(messages) > 0 and messages[-1]["role"] == "user":
                    messages.pop()
                
        except EOFError:
            signal_handler(None, None)


if __name__ == "__main__":
    main()
