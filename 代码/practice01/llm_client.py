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


def call_llm(env, prompt):
    base_url = env.get("LLM_BASE_URL", "").rstrip("/")
    api_key = env.get("LLM_API_KEY", "")
    model = env.get("LLM_MODEL", "gpt-3.5-turbo")
    
    if not base_url or not api_key:
        raise ValueError("请在 .env 文件中配置 LLM_BASE_URL 和 LLM_API_KEY")
    
    url = f"{base_url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
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
    
    start_time = time.time()
    
    try:
        with request.urlopen(req, timeout=timeout) as response:
            end_time = time.time()
            response_data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as e:
        end_time = time.time()
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"API 请求失败 (HTTP {e.code}): {error_body}")
    except error.URLError as e:
        end_time = time.time()
        raise RuntimeError(f"网络连接失败: {e.reason}")
    
    elapsed_time = end_time - start_time
    
    usage = response_data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    
    content = response_data["choices"][0]["message"]["content"]
    
    tokens_per_second = completion_tokens / elapsed_time if elapsed_time > 0 and completion_tokens > 0 else 0
    
    result = {
        "content": content,
        "model": response_data.get("model", model),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "elapsed_time": elapsed_time,
        "tokens_per_second": tokens_per_second
    }
    
    return result


def main():
    print("=" * 60)
    print("Practice 01: 原生 HTTP 库调用 LLM")
    print("=" * 60)
    
    try:
        env = load_env()
        print("[OK] 环境配置加载成功")
        print(f"  API: {env.get('LLM_BASE_URL')}")
        print(f"  模型: {env.get('LLM_MODEL')}")
        print()
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return
    
    prompt = "请用3句话介绍Python语言的特点"
    
    print(f"提问: {prompt}")
    print("-" * 60)
    
    try:
        result = call_llm(env, prompt)
        
        print("回答:")
        print(result["content"])
        print()
        print("-" * 60)
        print("[性能统计]")
        print(f"  模型:           {result['model']}")
        print(f"  输入 tokens:    {result['prompt_tokens']}")
        print(f"  输出 tokens:    {result['completion_tokens']}")
        print(f"  总 tokens:      {result['total_tokens']}")
        print(f"  耗时:           {result['elapsed_time']:.2f} 秒")
        print(f"  生成速度:       {result['tokens_per_second']:.2f} tokens/秒")
        
    except Exception as e:
        print(f"[ERROR] 调用失败: {e}")


if __name__ == "__main__":
    main()
