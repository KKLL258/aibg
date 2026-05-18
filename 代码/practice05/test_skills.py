import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SKILLS_ROOT = Path(__file__).parent.parent / ".agents" / "skills"

from chat_client import list_available_skills, load_skill_content

print("=" * 60)
print("测试技能系统功能")
print("=" * 60)
print(f"技能目录: {SKILLS_ROOT}")
print(f"技能目录存在: {SKILLS_ROOT.exists()}")
print()

print("1. 测试 list_available_skills 函数...")
result = list_available_skills()
print(f"   结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
print()

if result.get("success") and result.get("skills"):
    first_skill = result["skills"][0]["name"]
    print(f"2. 测试 load_skill_content 函数 - 加载技能: {first_skill}...")
    skill_result = load_skill_content(first_skill)
    print(f"   结果: {json.dumps(skill_result, ensure_ascii=False, indent=2)}")
else:
    print("2. 没有可用的技能进行测试")

print()
print("3. 测试加载不存在的技能...")
not_found = load_skill_content("不存在的技能")
print(f"   结果: {json.dumps(not_found, ensure_ascii=False, indent=2)}")

print()
print("=" * 60)
print("测试完成！")
print("=" * 60)
