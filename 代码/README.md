# AI 智能体开发实战教程

基于 Python 的 AI 智能体开发从零到实战教学项目。

---

## 📋 环境准备

### 环境配置
- Python 版本：3.12+
- 虚拟环境：`venv`
- LLM 后端：OpenAI 兼容协议（本地模型/云端模型）

### 快速开始
1. 复制环境变量模板并配置
   ```bash
   copy env.example .env
   ```
2. 编辑 `.env` 文件，填入你的 LLM 配置
3. 运行对应练习脚本

---

## 📚 课程目录

| 序号 | 练习目录 | 文件名 | 教学目标 & 知识点 |
|------|---------|--------|-----------------|
| **01** | `practice01/` | `llm_client.py` | ✅ **原生 HTTP 库调用 LLM** |
| | | | 🔹 使用 Python 标准库 `urllib` 发送 HTTP 请求<br>🔹 不依赖 openai SDK，理解底层协议<br>🔹 读取 `.env` 环境变量配置<br>🔹 统计 Token 消耗 & 计算生成速度<br>🔹 完整的错误处理机制 |
| **02** | `practice02/` | `chat_stream.py` | ✅ **流式多轮对话客户端** |
| | | | 🔹 SSE 流式输出实时显示，模拟 ChatGPT 打字效果<br>🔹 终端交互式输入，持续对话<br>🔹 历史消息自动维护上下文<br>🔹 Ctrl+C 优雅退出处理<br>🔹 每轮对话性能统计 |
| | | `tool_chat.py` | ✅ **系统提示词驱动工具调用** |
| **03** | `practice03/` | `chat_compression.py` | ✅ **聊天历史自动总结压缩** |
| | | | 🔹 智能阈值检测：超过5轮对话或3000字符自动触发<br>🔹 70/30 智能分割：旧内容总结压缩，新内容完整保留<br>🔹 LLM 驱动的智能摘要，保留关键上下文<br>🔹 上下文长度可视化统计<br>🔹 压缩率计算与效果展示 |
| | | `chat_memory.py` | ✅ **聊天记忆系统 + 5W信息提取** |
| | | | 🔹 **功能1: 5W结构化记忆提取** - 每5轮自动提取 Who/What/When/Where/Why<br>🔹 **本地持久化存储** - D:\chat-log\log.txt 增量写入，自动建目录文件<br>🔹 **双模式搜索触发** - `/search` 指令 + 语义识别"查找聊天历史"<br>🔹 **RAG增强回答** - 历史记录注入上下文，实现记忆检索<br>🔹 **记忆永不丢失** - 独立于对话窗口的外部记忆库 |
| | | | 🔹 通过系统提示词教 LLM 输出 JSON 格式调用<br>🔹 6个内置工具函数：文件操作 + 网络访问<br>🔹 list_directory - 列出目录及文件属性<br>🔹 rename_file / delete_file - 文件重命名、删除<br>🔹 create_file / read_file - 创建、读取文件<br>🔹 curl_request - 模拟 curl 访问网页<br>🔹 自动解析并执行工具调用，多轮调用循环 |
| | | `openai_tool_chat.py` | ✅ **OpenAI 标准 Function Calling** |
| | | | 🔹 使用 OpenAI 官方标准协议<br>🔹 结构化 tools 参数传递<br>🔹 并行工具调用支持<br>🔹 自动多轮调用循环 |
| **04** | `practice04/` | `chat_client.py` | ✅ **终极全功能 Agent - 完整整合版** |
| | | | 🔹 **📚 知识库 RAG** - anythingllm_query 语义检索，自动列出文档<br>🔹 **🧠 上下文压缩** - 5轮/3000字符自动触发，70%内容智能压缩<br>🔹 **💾 5W 记忆提取** - 每5轮后台线程自动提取 Who/What/When，持久化本地日志<br>🔹 **🔍 历史记忆搜索** - `/search` 命令 + 语义识别"查找聊天历史"<br>🔹 **🌐 全网爬取能力** - curl_request 访问任意外部网站，20000字符完整支持 ANSI 艺术<br>🔹 **📁 文件操作系统** - 6个工具函数：list/rename/delete/create/read<br>🔹 **🕐 时间感知能力** - get_current_datetime 知道今天几号现在几点<br>🔹 **⚡ 流式输出体验** - SSE 逐字输出打字机效果<br>🔹 **🔧 15次工具调用上限** - 支持复杂推理链路 |

---

## 📖 练习详情

---

### ✅ Practice 01: 原生 HTTP 库调用 LLM

**📂 文件位置：** `practice01/llm_client.py`

#### 🎯 教学目标
1. **理解 OpenAI API 协议本质**
   - 认识到 LLM API 本质就是 HTTP POST 请求
   - 理解请求头、请求体的格式
   - 掌握 JSON 数据序列化与反序列化

2. **掌握 Python 标准库使用**
   - `urllib.request` - 标准 HTTP 客户端
   - `json` - JSON 数据处理
   - `time` - 精确计时
   - `pathlib` - 跨平台路径处理

3. **工程化能力培养**
   - 配置文件的读取与管理
   - 异常处理与错误提示
   - 性能指标统计（时间、Token、速度）

#### 💡 核心代码讲解

**1. 环境变量读取**
```python
def load_env():
    # 纯 Python 实现，不依赖 python-dotenv 第三方库
    env_path = Path(__file__).parent.parent / ".env"
    # 逐行解析 key=value 格式
```

**2. 标准 HTTP 请求**
```python
from urllib import request, error

data = json.dumps(payload).encode("utf-8")
req = request.Request(url, data=data, headers=headers, method="POST")

with request.urlopen(req, timeout=timeout) as response:
    response_data = json.loads(response.read().decode("utf-8"))
```

**3. 性能统计**
```python
start_time = time.time()
# ... API 调用 ...
elapsed_time = end_time - start_time
tokens_per_second = completion_tokens / elapsed_time
```

#### 🚀 运行方式

```bash
# 方式1：使用启动脚本（推荐）
cd practice01
run.bat

# 方式2：直接运行
py -3.12 practice01/llm_client.py
```

#### 📊 示例输出
```
============================================================
Practice 01: 原生 HTTP 库调用 LLM
============================================================
[OK] 环境配置加载成功
  API: http://localhost:11434/v1
  模型: qwen:7b

提问: 请用3句话介绍Python语言的特点
------------------------------------------------------------
回答:
Python 是一门语法简洁且易读的脚本语言...

------------------------------------------------------------
[性能统计]
  模型:           qwen:7b
  输入 tokens:    17
  输出 tokens:    108
  总 tokens:      125
  耗时:           2.85 秒
  生成速度:       37.89 tokens/秒
```

---

### ✅ Practice 02: 流式多轮对话客户端

**📂 文件位置：** `practice02/chat_stream.py`

#### 🎯 教学目标
1. **掌握 SSE 流式输出协议**
   - 理解 `stream: True` 参数含义
   - 逐行解析 `data: {...}` 格式
   - 实时 flush 输出到终端，实现打字机效果
   - 处理结束标记 `data: [DONE]`

2. **终端交互式程序设计**
   - `input()` 函数获取用户输入
   - `sys.stdout.flush()` 实时输出
   - `signal` 信号处理捕获 Ctrl+C
   - 无限循环实现持续对话

3. **多轮对话上下文管理**
   - `messages` 列表维护对话历史
   - 自动追加用户提问和助手回答
   - 上下文记忆机制是 Agent 的基础
   - 错误回滚机制（调用失败时弹出历史）

#### 💡 核心代码讲解

**1. 流式输出核心实现**
```python
def print_stream(content):
    sys.stdout.write(content)
    sys.stdout.flush()  # 关键：立即输出，不缓冲

# 逐块解析 SSE 响应
for line in response:
    line = line.decode("utf-8").strip()
    if line.startswith("data: "):
        chunk_data = json.loads(line[6:])
        content = chunk_data["choices"][0]["delta"].get("content", "")
        if content:
            print_stream(content)
```

**2. Ctrl+C 优雅退出**
```python
import signal

def signal_handler(sig, frame):
    print("\n\n[系统] 对话已结束，再见！")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
```

**3. 上下文自动维护**
```python
messages = []

while True:
    user_input = input("[你] ")
    messages.append({"role": "user", "content": user_input})
    
    response, stats = call_llm_stream(env, messages)

---

### ✅ Practice 02: 系统提示词驱动工具调用

**📂 文件位置：** `practice02/tool_chat.py`

#### 🎯 教学目标
1. **理解原生工具调用原理**
   - 不依赖 OpenAI Function Calling 协议
   - 通过系统提示词教 LLM 输出 JSON 格式
   - 正则表达式智能解析工具调用
   - 结果回传形成完整调用链路

2. **6个内置工具函数**
   - `list_directory` - 列出目录，包含文件大小、修改时间
   - `rename_file` / `delete_file` - 文件重命名、删除
   - `create_file` / `read_file` - 创建并写入、读取内容
   - ✅ **新增** `curl_request` - 模拟 curl 访问网页，自动编码处理

3. **通用 Agent 架构思想**
   - Thought → Action → Observation 循环
   - 最多支持 5 轮连续工具调用
   - 最终用自然语言总结结果

#### 💡 核心代码讲解

**1. 系统提示词工程**
```python
SYSTEM_PROMPT = \"\"\"你拥有以下6个工具可以调用：

【工具6】curl_request - 模拟 curl 访问网页
参数：
  - url: 网页完整 URL

调用规则：请输出严格的JSON格式：
```json
{{"name": "工具名", "parameters": {{"参数名": "参数值"}}}}
```
\"\"\"
```

**2. 智能 JSON 解析器**
```python
def parse_tool_call(content):
    # 1. 先解析 ```json ... ``` 代码块
    pattern = r'```json\s*(\{.*?\})\s*```'
    
    # 2. 失败则尝试直接解析 JSON
    try:
        tool_call = json.loads(content)
    except:
        pass
```

**3. 工具执行与结果反馈**
```python
result = execute_tool(tool_call)

# 结果回传给 LLM，继续思考
messages.append({
    "role": "user",
    "content": f"工具执行结果：{json.dumps(result)}。请基于结果继续处理..."
})
```

#### 🚀 运行方式

```bash
# 运行工具调用对话客户端
cd practice02
run_tool.bat
```

#### 💻 运行示例

```
[系统] 已加载 6 个工具函数:
  1. list_directory  - 列出目录文件及属性
  2. rename_file     - 重命名文件
  3. delete_file     - 删除文件
  4. create_file     - 创建文件并写入内容
  5. read_file       - 读取文件内容
  6. curl_request    - 模拟 curl 访问网页

[你] 帮我访问百度首页，看看标题
[思考中...]

[调用工具] curl_request
  参数: {"url": "https://www.baidu.com"}
  结果: {
    "success": true,
    "status_code": 200,
    "content_length": 2443,
    "content": "<html>...<title>百度一下，你就知道</title>..."
  }

[AI] 百度首页访问成功！页面标题是：百度一下，你就知道
```
    
    messages.append({"role": "assistant", "content": response})
    # messages 列表越来越长，包含完整历史
```

---

### ✅ Practice 03: 聊天历史自动总结压缩

**📂 文件位置：** `practice03/chat_compression.py`

#### 🎯 教学目标
1. **上下文窗口管理技术**
   - 理解 Token 限制对长对话的影响
   - 掌握滑动窗口与总结压缩两种策略
   - 在"记忆完整性"和"成本控制"之间取得平衡
   - 这是生产级 Agent 必备的核心能力

2. **智能阈值触发机制**
   - 双条件触发：对话轮数 OR 字符长度
   - 超过5轮对话自动触发总结
   - 上下文长度超过3000字符启动压缩
   - 提前干预，避免触发 LLM Token 限制

3. **70/30 智能分割算法**
   - 前70%历史内容：LLM 智能总结压缩
   - 后30%近期内容：完整原文保留
   - 兼顾长期记忆的完整性和近期对话的准确性
   - 可自定义分割比例适配不同场景

4. **工程化指标监控**
   - 实时计算上下文总长度
   - 压缩前后字符数对比
   - 可视化展示压缩率百分比
   - 便于优化参数和效果评估

#### 💡 核心代码讲解

**1. 阈值检测与触发逻辑**
```python
def check_and_compress(env, messages):
    total_rounds = len(messages) // 2
    context_length = calculate_context_length(messages)
    
    if total_rounds > 5 or context_length > 3000:
        return compress_chat_history(env, messages)
    return messages
```

**2. 70/30 智能分割算法**
```python
def compress_chat_history(env, messages):
    total_messages = len(messages)
    split_index = int(total_messages * 0.7)  # 关键点
    
    messages_to_compress = messages[:split_index]  # 前70%压缩
    messages_to_keep = messages[split_index:]       # 后30%保留
```

**3. LLM 驱动智能总结**
```python
summary_prompt = f"""请对以下对话历史进行简洁的总结
要求：
1. 用简洁的语言概括对话的主要内容
2. 保留对话中的关键信息、事实和约定
3. 不要遗漏重要的上下文信息

对话历史：
{conversation_text}

总结："""

summary = call_llm_simple(env, [{"role": "user", "content": summary_prompt}])

# 用 system 消息插入总结摘要
summary_message = {
    "role": "system",
    "content": f"【对话历史总结】{summary}"
}

new_messages = [summary_message] + messages_to_keep
```

**4. 压缩效果量化评估**
```python
old_length = calculate_context_length(messages)
new_length = calculate_context_length(new_messages)
compression_rate = (1 - new_length/old_length) * 100

print(f"原长度: {old_length} 字符")
print(f"新长度: {new_length} 字符")
print(f"压缩率: {compression_rate:.1f}%")
```

#### 🚀 运行方式

```bash
# 方式1：使用启动脚本（推荐）
cd practice03
run.bat

# 方式2：直接运行
py -3.12 practice03/chat_compression.py
```

#### 💻 运行示例

```
============================================================
Practice 03: 聊天历史自动总结压缩
============================================================
[系统] 超过5轮对话或上下文长度超过3000字符将自动触发总结压缩

[你] 请记住以下信息：我叫张三，今年28岁，职业是程序员
[AI] 好的张三，我记住了！你是一位28岁的程序员，很高兴认识你。

[你] 我喜欢Python，正在学习Agent开发...（第6轮对话开始）

[系统] 触发自动总结：对话轮数超过5轮（当前 6 轮）
[系统] 总消息数: 12, 压缩前 8 条，保留后 4 条
[系统] 压缩完成！原长度: 3500 字符，新长度: 800 字符, 压缩率: 77.1%

[AI] 继续回答你的问题...
  ─── 本次对话统计 ───
  历史消息数: 3 轮
  上下文长度: 920 字符  ✅ 已被压缩
```

#### 🎓 进阶思考
- **为什么用 70/30 分割？** 70% 是经验值，确保总结有足够内容同时保留近期对话的完整上下文
- **总结为什么用 system 角色？** 告诉 LLM 这是背景知识，不要和用户当前提问混淆
- **触发时机为什么是第5轮后？** 既保证对话流畅性，又不会等溢出后才补救，属于预防性措施
- **可以优化的方向：**
  - 按 Token 数精确计算而非字符数
  - 滚动式渐进总结，不是一次性全部重写
  - 重要消息标记为永不压缩

---

### ✅ Practice 03: 聊天记忆系统 + 5W信息提取

**📂 文件位置：** `practice03/chat_memory.py`

#### 🎯 教学目标
1. **Agent 外部记忆系统架构**
   - 上下文记忆 = 短期记忆（在 messages 数组中）
   - 知识库记忆 = 长期记忆（在外部文件/数据库中）
   - 这是 Agent 实现"永不遗忘"的核心技术路线
   - 理解 RAG（检索增强生成）的本质

2. **5W 结构化信息提取**
   - 新闻传播学经典方法论：Who/What/When/Where/Why
   - 将非结构化的自然语言转化为结构化数据
   - 每5轮对话自动执行一次，增量构建知识库
   - 理解结构化数据对检索的重要性

3. **本地持久化存储机制**
   - `Path.mkdir(parents=True)` 自动创建目录链
   - `open(..., "a")` 追加模式实现增量更新
   - 统一的编码规范（UTF-8 无 BOM）
   - 文件不存在时自动初始化

4. **双模式意图识别引擎**
   - **指令模式：** `/search` 前缀精确匹配，立即触发
   - **语义模式：** LLM 判断用户是否表达了搜索意图
   - 两种模式互为补充，兼顾精确性和自然度
   - 这是 Function Calling 的最小实现原型

5. **检索增强生成 (RAG) 最简实现**
   - 检索：读取本地日志文件
   - 增强：将历史记录拼接到 system prompt
   - 生成：基于增强后的上下文回答用户问题
   - 这就是 90% RAG 应用的核心原理

#### 💡 核心代码讲解

**1. 5W 关键信息提取提示词**
```python
system_prompt = """你是一个关键信息提取专家。请从对话中按照5W规则提取：
✅ 必选：Who(谁), What(什么事)
⚪ 可选：When(何时), Where(何地), Why(为什么)

输出格式：
=== 提取时间：YYYY-MM-DD HH:MM:SS ===
Who: 
What:
When:
Where:
Why:
===============================
"""
```

**2. 本地文件持久化**
```python
LOG_FILE = Path("D:/chat-log/log.txt")

def ensure_log_file():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)  # 自动创建目录
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("=== 聊天关键信息记录 ===\n\n")

def append_to_log(content):
    ensure_log_file()
    with open(LOG_FILE, "a", encoding="utf-8") as f:  # 'a' = append 追加
        f.write(content + "\n")
```

**3. 双模式搜索意图识别**
```python
def check_search_intent(env, user_input):
    # 模式1: 精确指令匹配 - 立即生效，无需 LLM
    if user_input.strip().lower().startswith("/search"):
        return True, user_input.replace("/search", "", 1).strip()
    
    # 模式2: LLM 语义理解 - 处理自然语言
    result = call_llm_simple(env, [
        {"role": "system", "content": "判断是否要搜索历史。只回答 YES 或 NO"},
        {"role": "user", "content": f"判断：{user_input}"}
    ])
    
    return result.strip().upper() == "YES", user_input
```

**4. 极简 RAG 检索增强**
```python
def search_chat_history(env, query):
    # 第1步：Retrieve 检索 - 从外部记忆读取
    history_log = read_chat_log()
    
    # 第2步：Augment 增强 - 注入到提示词
    system_prompt = f"""你是聊天历史助手。基于以下记录回答问题：
{history_log}

请根据历史记录准确回答。如果没有相关信息请如实说明。"""
    
    # 第3步：Generate 生成 - 用增强后的上下文调用 LLM
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]
```

**5. 每5轮自动触发机制**
```python
chat_count = 0

while True:
    response, stats = call_llm_stream(env, messages)
    chat_count += 1  # 计数
    
    if chat_count % 5 == 0:  # 每5轮执行一次
        print(f"[系统] 每5轮自动提取关键信息中...")
        key_info = extract_key_info(env, messages, 5)
        append_to_log(key_info)
        print(f"[系统] 关键信息已写入日志文件")
```

#### 🚀 运行方式

```bash
# 方式1：使用启动脚本（推荐）
cd practice03
run_memory.bat

# 方式2：直接运行
py -3.12 practice03/chat_memory.py
```

#### 💻 功能演示

**🔹 演示1：5W 自动提取（第5轮自动触发）**
```
[你] 我叫张三，是一名程序员，今天我在公司学习Agent开发
[AI] 你好张三！很高兴认识一位热爱学习的程序员...

[你] 我打算明天在家里继续做这个项目...
[AI] 好的，开发Agent确实需要反复练习...

[系统] 每5轮自动提取关键信息中...
[系统] 关键信息已写入日志文件: D:\chat-log\log.txt
=== 提取时间：2026-04-15 16:30:00 ===
Who: 张三（程序员）
What: 学习Agent开发，打算做相关项目
When: 今天（学习）、明天（继续开发）
Where: 今天在公司，明天在家里
Why: 学习和项目开发需要
===============================
```

**🔹 演示2：双模式搜索**
```
# 方式A：指令模式
[你] /search 张三是谁
[系统] 正在检索聊天历史记录...
[AI] 根据聊天历史记录，张三是一名程序员，正在学习Agent开发...

# 方式B：自然语言模式（语义识别）
[你] 还记得我们之前聊了什么吗？
[系统] 正在检索聊天历史记录...
[AI] 好的，让我回顾一下历史对话记录。我们之前聊了...
```

**🔹 日志文件内容示例**
```
=== 聊天关键信息记录 ===

=== 提取时间：2026-04-15 16:30:00 ===
Who: 张三（程序员）
What: 学习Agent开发
When: 今天在学习
Where: 公司
Why: 技术学习
===============================

=== 提取时间：2026-04-15 16:40:00 ===
...
```

#### 🎓 进阶思考
- **为什么用 5W 提取？** 结构化数据便于后续检索、统计、分析，远优于纯文本
- **为什么每5轮提取一次？** 平衡实时性和成本，信息越新价值越高，也更完整
- **RAG 为什么有效？** LLM 的知识有截止日期，外部记忆可以实时更新
- **下一步进化方向：**
  - 用向量数据库存储，支持语义相似度检索
  - 每条记忆添加元数据（时间、情绪值、重要性评分）
  - 记忆衰减机制：不重要的信息自动遗忘
  - 记忆反思：定期对所有记录做二次总结

#### 🚀 运行方式

```bash
# 方式1：使用启动脚本（推荐）
cd practice02
run.bat

# 方式2：直接运行
py -3.12 practice02/chat_stream.py
```

#### 💬 示例对话

```
============================================================
Practice 02: 流式对话客户端
============================================================
[OK] 环境配置加载成功
[系统] 欢迎！输入内容开始聊天，按 Ctrl+C 退出
------------------------------------------------------------

[你] 你好，我叫小明

[AI] 你好小明！很高兴认识你。有什么我可以帮助你的吗？

  ─── 本次对话统计 ───
  历史消息数: 1 轮
  输出 tokens: 25
  耗时: 0.85 秒
  生成速度: 29.41 tokens/秒
------------------------------------------------------------

[你] 还记得我叫什么吗？

[AI] 当然记得！你叫小明 😊

  ─── 本次对话统计 ───
  历史消息数: 2 轮
  输出 tokens: 12
  耗时: 0.42 秒
  生成速度: 28.57 tokens/秒
```

> 💡 **重要发现：**
> 第二问中，AI 记住了你叫"小明"！
> 这就是 **上下文记忆** 的力量，也是所有智能体的基础。

---

## ⚙️ 环境配置说明

### env.example 模板变量
| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `LLM_BASE_URL` | OpenAI 兼容 API 地址 | `http://localhost:11434/v1` |
| `LLM_API_KEY` | API 密钥 | `sk-xxxxxx` |
| `LLM_MODEL` | 模型名称 | `qwen:7b`, `gpt-3.5-turbo` |
| `LLM_TEMPERATURE` | 采样温度（可选） | `0.7` |
| `LLM_MAX_TOKENS` | 最大生成长度（可选） | `2000` |
| `LLM_TIMEOUT` | 请求超时秒数（可选） | `60` |

### 支持的 LLM 后端
| 服务商 | BASE_URL |
|--------|----------|
| **Ollama 本地** | `http://localhost:11434/v1` |
| **LM Studio** | `http://localhost:1234/v1` |
| **OpenAI** | `https://api.openai.com/v1` |
| **通义千问** | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| **豆包** | `https://ark.cn-beijing.volces.com/api/v3` |

---

## 🔧 常见问题

### Q: 为什么用 `py -3.12` 而不是直接 `python`？
A: 系统可能存在多个 Python 版本，`py -3.12` 确保使用正确的版本

### Q: UnicodeEncodeError 编码错误怎么办？
A: Windows GBK 编码问题，已修复使用纯 ASCII 状态标识

### Q: 网络连接超时？
A: 检查你的 LLM 后端是否启动，或者网络代理配置

---

## 📌 项目结构
```
trce/
├── .gitignore              # Git 排除规则
├── .env                    # 你的私有配置（不提交）
├── env.example             # 环境变量模板
├── README.md               # 本文件
├── venv/                   # 虚拟环境
├── practice01/             # 第1课：单次请求
│   ├── llm_client.py       # 非流式HTTP客户端
│   ├── run.bat             # Windows 启动脚本
│   └── run.ps1             # PowerShell 启动脚本
└── practice02/             # 第2课：流式多轮对话
    ├── chat_stream.py      # 流式聊天 + 上下文记忆
    ├── run.bat             # Windows 启动脚本
    └── run.ps1             # PowerShell 启动脚本
```

---

## 🎓 教学理念

**本教程特点：**
1. ✅ 从零开始，不跳过基础
2. ✅ 优先使用标准库，理解原理
3. ✅ 每一行代码都有其教学意义
4. ✅ 从 HTTP 协议到高级封装逐步深入

---

---

### ✅ Practice 04: 终极全功能 Agent - 完整整合版

**📂 文件位置：** `practice04/chat_client.py`

#### 🎯 教学目标
整合 Practice 01-03 的全部教学成果，构建一个**生产可用的完整 Agent 系统**，实现：
- **短期记忆**（上下文自动压缩）
- **长期记忆**（5W信息提取持久化）
- **外部知识**（RAG知识库语义检索）
- **行动能力**（联网+文件操作）

这是本课程的**结业项目**，通过本实验你将掌握企业级 Agent 的完整架构设计。

---

## 🚀 新功能使用指南

启动方式：
```bash
cd practice04
run.bat
```

---

### 📚 功能1: RAG 知识库检索
**自动触发条件：**
- 提到「文档仓库」、「文件仓库」、「知识库」、「查文档」
- 需要从私有资料中检索信息

**用法示例：**
```
[你] 列出知识库中的所有文件
[你] 在知识库中查找关于Python的内容
```

**执行效果：**
```
[调用工具] anythingllm_list_documents
  ✓ 返回 3 个文档：env.example、README.md、test.txt

[调用工具] anythingllm_query
  参数: {"message": "Python"}
  ✓ 找到相关文档片段...
```

---

### 🧠 功能2: 聊天历史自动压缩
**自动触发条件（无需手动操作）：**
- ✅ 对话超过 **5 轮** 自动触发
- ✅ 上下文超过 **3000 字符** 自动触发

**压缩策略：**
- **前 70%** 的历史：LLM 智能总结压缩
- **后 30%** 的内容：完整原文保留

**效果展示：**
```
[系统] 触发自动总结：对话轮数超过5轮（当前 6 轮）
[系统] 正在自动压缩聊天历史...
[系统] ✓ 压缩完成！原长度: 4500 → 新长度: 1200 (压缩率: 73.3%)
```

---

### 💾 功能3: 5W 信息自动提取记忆
**自动触发（后台静默执行）：**
- 每 **5 轮对话** 在后台线程自动执行
- 提取 Who/What/When/Where/Why 结构化信息
- 持久化写入 `D:\chat-log\log.txt`

**效果展示：**
```
[系统] 后台提取关键信息中...
[系统] ✓ 5W记忆已更新至日志文件

=== 2026-04-22 15:30:00 ===
人物：用户与智能助手
事件：测试并验证了Agent的联网与天气查询功能
==
```

---

### 🔍 功能4: 本地聊天历史搜索
**触发方式（2种）：**
1. **命令式：** `/search 关键词`
2. **语义式：** "查找我们刚才聊了什么"、"搜索聊天历史"

**用法示例：**
```
[你] /search 天气
[你] 查找我们之前聊过的关于Python的内容
```

> 💡 **意图识别优化：**
> 只有明确提到「聊天历史」、「聊天记录」才会触发历史搜索
> 问天气、查资料等不会再误触发！

---

### 🌐 功能5: 全网数据爬取
**自动触发条件：**
- 查询天气、实时信息、最新数据
- 任何 LLM 训练数据截止后发生的事件
- 需要访问外部网站获取内容

**用法示例：**
```
[你] 成都现在天气怎么样
[你] 帮我访问百度首页看看标题
[你] 查询明天青城山的天气
```

**执行效果：**
```
[调用工具] curl_request
  参数: {"url": "https://wttr.in/成都?format=3"}
  ✓ 返回: chengdu: ☀️   +23°C
```

> 💡 **重要提示：**
> wttr.in 只支持**县级以上城市**，查「青城山」会自动用「都江堰」替代并说明

---

### 📁 功能6: 文件操作系统
**内置 6 个工具函数：**
| 工具名 | 功能 |
|--------|------|
| `list_directory` | 列出目录文件及属性 |
| `create_file` | 创建文件并写入内容 |
| `read_file` | 读取文件内容 |
| `rename_file` | 重命名文件 |
| `delete_file` | 删除文件 |

**用法示例：**
```
[你] 列出当前目录的文件
[你] 创建一个 test.py 文件写个Hello World
[你] 把它重命名为 demo.py
```

---

### 🕐 功能7: 时间感知能力
**自动触发条件：**
- 询问现在几点、今天几号、星期几
- 涉及时间判断的问题

**用法示例：**
```
[你] 现在是什么时间
[你] 今天几号
```

**执行效果：**
```
[调用工具] get_current_datetime
  ✓ 返回: 2026年4月22日 星期三 15:45:30
```

> ✅ Agent 再也不会回答"作为一个AI，我不知道当前时间"了！

---

### ⚡ 流式输出体验
**所有最终回答都采用 SSE 逐字输出：**
```
[AI] 根据查询结果，成都当前天气晴朗，
气温 23°C，建议出行携带防晒用品。
```
*（打字机效果，每个字逐个打出）*

---

### 🔧 工具调用优化
**最大工具调用次数：** 从 5 次 → **15 次**

支持复杂推理链路：
```
1. 列出知识库文档
2. 读取 README.md
3. 联网查询相关资料
4. 创建总结文件
...（最多支持15步）
```

---

#### 🎯 核心架构设计

**四分层能力模型：**
```
┌─────────────────────────────────────────────────────┐
│                  终极全功能 Agent                   │
├─────────────┬─────────────┬─────────────┬───────────┤
│  短期记忆   │  长期记忆   │  外部知识   │  行动能力  │
│  上下文压缩 │  5W提取日志 │  RAG向量库  │  联网+文件 │
└─────────────┴─────────────┴─────────────┴───────────┘
```

**工程化亮点：**
- ✅ **后台线程提取** - 5W记忆不阻塞主聊天流程
- ✅ **严格意图规则** - 宁可少触发，不要误触发
- ✅ **数据源边界** - 明确告知 LLM 每个工具的能力范围
- ✅ **错误降级处理** - 任何异常都有友好提示，不崩溃
    "sources": response_data.get("sources", []),  # 引用的文档来源
    "metadata": {
        "close": response_data.get("close", False),
        "error": response_data.get("error", None),
        "id": response_data.get("id", "")
    }
}
```

#### 🚀 环境准备

**步骤1：启动 AnythingLLM 服务**
```bash
# 确保 AnythingLLM 正在运行
# 默认端口: http://localhost:3001
```

**步骤2：配置 API Key**
```bash
# 在 .env 文件中配置
ANYTHINGLLM_API_KEY=你的API密钥
# 在 AnythingLLM 工作区 > 设置 > API 中生成
```

**步骤3：验证 API**
```bash
# 浏览器访问 API 文档
http://localhost:3001/api/docs/
```

#### 🚀 运行方式

```bash
# 方式1：使用启动脚本（推荐）
cd practice04
run.bat

# 方式2：直接运行
python practice04/chat_client.py
```

#### 💻 运行示例

```
============================================================
Practice 04: AnythingLLM 知识库集成
============================================================
[OK] 环境配置加载成功
[系统] 已加载 6 个工具函数:
  1. anythingllm_query - 查询AnythingLLM文档仓库（新功能！）
[提示] 触发知识库查询关键词：
  「文档仓库」、「文件仓库」、「仓库」、「知识库」、「查文档」
------------------------------------------------------------
[你] 从文档仓库中查询关于Python性能优化的方法

[思考中...]

[调用工具] anythingllm_query
  参数: {"message": "关于Python性能优化的方法", "workspace": "AI"}
  结果: {
    "success": true,
    "workspace": "AI",
    "query": "关于Python性能优化的方法",
    "response": "Python性能优化的主要方法包括：1. 使用内置数据结构...",
    "sources": [
      {"source": "Python性能优化指南.pdf", "page": 12},
      {"source": "高效Python编程技巧.md", "page": 5}
    ]
  }

[AI] 根据文档仓库检索到的信息，Python性能优化主要有以下方法：

1. **使用内置数据结构** - list、dict、set 等内置类型经过C优化
2. **避免全局变量** - 局部变量访问速度比全局变量快
3. **使用列表推导** - 比 for 循环 + append 快约2倍
4. **内置函数优先** - 使用 len()、map() 等内置函数
5. **选择合适的算法** - 时间复杂度是性能的决定性因素

参考来源：Python性能优化指南.pdf、高效Python编程技巧.md
```

#### 🎓 进阶思考
- **为什么用 subprocess + curl 而不是 requests 库？**
  - 减少第三方依赖，降低环境配置复杂度
  - curl 是通用工具，跨平台一致性好
  - 便于调试，命令行可以直接复现
  - 理解 HTTP 客户端的底层实现

- **为什么需要关键词触发？**
  - 减少误调用，降低 RAG 成本
  - 用户意图明确时直接命中
  - 可扩展为向量相似度触发

- **可以优化的方向：**
  - sources 来源格式化展示
  - 多工作区智能路由
  - 流式知识库响应
  - 缓存重复查询结果

---

> 😊 **知其然，知其所以然**
>
> 我们不从 `pip install openai` 开始，
> 而是从 `urllib.request` 开始，
> 让你真正理解 AI 智能体的底层原理。
