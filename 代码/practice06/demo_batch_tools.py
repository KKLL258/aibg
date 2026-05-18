import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))

from chat_client import *

print("=" * 70)
print("批量处理工具演示")
print("=" * 70)
print()

print("【1】测试 find_files - 递归查找 .py 文件")
print("-" * 70)
result = find_files(directory_path="../practice05", pattern="*.py", max_depth=2)
print(f"找到 {result.get('total_matched')} 个 .py 文件:")
for f in result.get("files", []):
    print(f"  - {f.get('path')} ({f.get('size_bytes')} bytes)")
print()

print("【2】测试 search_files_by_content - 查找包含'def'的文件")
print("-" * 70)
result = search_files_by_content(directory_path="../practice05", keyword="def", file_pattern="*.py")
print(f"搜索了 {result.get('total_searched')} 个文件，找到 {result.get('total_matching')} 个包含'def'的文件:")
for f in result.get("matching_files", []):
    print(f"  - {f.get('path')}: {f.get('matching_lines_count')} 处匹配")
print()

print("【3】测试 batch_read_files - 批量读取多个文件")
print("-" * 70)
files_to_read = ["../practice05/chat_client.py", "../practice04/chat_client.py"]
result = batch_read_files(files_to_read, directory=".")
print(f"请求读取 {result.get('total_requested')} 个文件")
print(f"成功: {result.get('success_count')} 个, 失败: {result.get('failed_count')} 个")
for r in result.get("results", []):
    print(f"  ✓ {r.get('path')}: {r.get('size_bytes')} bytes {'(已截断)' if r.get('truncated') else ''}")
print()

print("【4】测试增强的上下文变量解析（支持列表推导式）")
print("-" * 70)

test_context = ChainedCallContext("测试")
test_context.context_variables["step_1_search_files_by_content_result"] = {
    "matching_files": [
        {"path": "file1.py"},
        {"path": "file2.py"},
        {"path": "file3.py"}
    ]
}

test_value = "${[f['path'] for f in step_1_search_files_by_content_result['matching_files']]}"
resolved = resolve_context_variables(test_value, test_context)
print(f"原始表达式: {test_value}")
print(f"解析结果: {resolved}")
print(f"类型: {type(resolved)}")
print()

print("=" * 70)
print("批量工具全部就绪！")
print("=" * 70)
print()
print("现在可以执行完整的多文件链式调用了:")
print("  python test_chained_demo.py")
print()
print("在聊天中可以这样使用:")
print('  /chain 查找 practice05 下所有包含"def"的 .py 文件，总结这些文件的内容')
print()
