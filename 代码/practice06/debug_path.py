import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

base_path = Path(__file__).parent.parent
print(f"脚本所在目录: {Path(__file__).parent}")
print(f"项目根目录: {base_path}")
print(f"practice05 目录存在吗: {(base_path / 'practice05').exists()}")
print(f"practice05 内容: {list((base_path / 'practice05').iterdir())}")

def debug_find_files(directory_path: str = ".", pattern: str = "*.py", max_depth: int = 3):
    import fnmatch
    
    target_path = (base_path / directory_path).resolve()
    print(f"\n目标路径: {target_path}")
    print(f"目标路径存在吗: {target_path.exists()}")
    
    project_root = Path(__file__).parent.parent.resolve()
    print(f"在项目根内: {str(target_path).startswith(str(project_root))}")
    
    matched_files = []
    
    def scan_dir(current_path, current_depth):
        if current_depth > max_depth:
            return
        
        for item in current_path.iterdir():
            if item.is_dir():
                scan_dir(item, current_depth + 1)
            elif item.is_file():
                rel_path = str(item.relative_to(project_root))
                if fnmatch.fnmatch(item.name, pattern):
                    print(f"  匹配: {item.name} -> {rel_path}")
                    matched_files.append({
                        "path": rel_path,
                        "name": item.name,
                    })
    
    scan_dir(target_path, 0)
    print(f"匹配文件数: {len(matched_files)}")
    return matched_files

print("\n--- 调用 find_files ---")
files = debug_find_files("practice05", "*.py", 2)
print(f"结果: {len(files)} 个文件")
