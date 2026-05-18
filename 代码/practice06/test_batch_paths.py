import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))

from chat_client import *

print("测试路径修正...")

print("\n1. find_files(directory_path='practice05', pattern='*.py')")
result = find_files(directory_path="practice05", pattern="*.py", max_depth=2)
print(f"   找到: {result.get('total_matched')} 个 .py 文件")
for f in result.get("files", []):
    print(f"      - {f.get('path')}")

print("\n2. search_files_by_content 在 practice05 搜索 'def'")
result = search_files_by_content(
    directory_path="practice05", 
    keyword="def", 
    file_pattern="*.py"
)
print(f"   搜索了 {result.get('total_searched')} 个文件")
print(f"   匹配 {result.get('total_matching')} 个文件")
for f in result.get("matching_files", []):
    print(f"      - {f.get('name')}: {f.get('matching_lines_count')} 处 def")

print("\n3. batch_read_files 读取匹配的文件")
paths = [f['path'] for f in result.get('matching_files', [])][:2]
print(f"   读取: {paths}")
result = batch_read_files(paths)
print(f"   成功: {result.get('success_count')}, 失败: {result.get('failed_count')}")

print("\n✅ 所有路径问题修复完成！")
