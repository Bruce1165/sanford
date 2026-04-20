#!/usr/bin/env python3
"""
Quick Verification Script - 快速验证系统功能

Purpose: 快速检查关键功能是否正常工作，确保没有回归
"""
import sys
import json
import sqlite3
from pathlib import Path

workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))
sys.path.insert(0, str(workspace_root / 'backend'))

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def test(name, result, error=""):
    """Print test result"""
    if result:
        print(f"  {GREEN}✓{RESET} {name}")
    else:
        print(f"  {RED}✗{RESET} {name}")
        if error:
            print(f"    {RED}Error: {error}{RESET}")
    return result

def print_section(title):
    """Print section header"""
    print(f"\n{YELLOW}{'='*60}{RESET}")
    print(f"{YELLOW}{title}{RESET}")
    print(f"{YELLOW}{'='*60}{RESET}\n")

all_passed = True

# Test 1: Configuration Files
print_section("1. 配置文件检查")
config_dir = workspace_root / 'config' / 'screeners'
config_files = list(config_dir.glob('*.json'))
test(f"配置文件目录存在", config_dir.exists())
test(f"配置文件数量正确 (14个)", len(config_files) == 14, f"found {len(config_files)} files")

for config_file in config_files:
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            test(f"配置文件格式正确: {config_file.name}",
                 'display_name' in config and 'parameters' in config)
    except Exception as e:
        test(f"配置文件读取失败: {config_file.name}", False, str(e))
        all_passed = False

# Test 2: Database
print_section("2. 数据库检查")
dashboard_db = workspace_root / 'data' / 'dashboard.db'

if dashboard_db.exists():
    conn = sqlite3.connect(str(dashboard_db))
    cursor = conn.cursor()

    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    test("screener_configs 表存在", 'screener_configs' in tables)
    test("screener_config_history 表存在", 'screener_config_history' in tables)

    # Check integrity
    cursor.execute("PRAGMA integrity_check;")
    integrity = cursor.fetchone()[0]
    test("数据库完整性检查", integrity == "ok", integrity)

    conn.close()
else:
    test("数据库文件存在", False, f"Database not found: {dashboard_db}")
    all_passed = False

# Test 3: Python Modules
print_section("3. Python 模块检查")
try:
    from backend.config_loader import ConfigLoader
    test("ConfigLoader 模块导入", True)

    config = ConfigLoader.load_from_file('er_ban_hui_tiao')
    test("ConfigLoader 加载配置", config is not None)

except Exception as e:
    test("ConfigLoader 模块", False, str(e))
    all_passed = False

try:
    from backend.validators import validate_screener_config_update
    test("Validators 模块导入", True)

    is_valid, error, _ = validate_screener_config_update({
        'parameters': {},
        'change_summary': 'test',
        'updated_by': 'test'
    })
    test("Validators 验证功能", is_valid, error)

except Exception as e:
    test("Validators 模块", False, str(e))
    all_passed = False

try:
    from backend.docstring_updater import DocstringUpdater
    test("DocstringUpdater 模块导入", True)
    # Quick test - generate a docstring
    test_config = {
        'display_name': 'Test',
        'description': 'Test desc',
        'category': 'Test',
        'parameters': {
            'TEST_PARAM': {
                'value': 10,
                'display_name': 'Test Param',
                'description': 'Test',
                'group': 'Test',
                'type': 'int',
                'default': 10
            }
        }
    }
    docstring = DocstringUpdater.generate_docstring('test', test_config, test_config['parameters'])
    test("DocstringUpdater 生成功能", docstring is not None and len(docstring) > 0)

except Exception as e:
    test("DocstringUpdater 模块", False, str(e))
    all_passed = False

try:
    import importlib.util
    base_file = workspace_root / 'screeners' / 'base_screener.py'
    spec = importlib.util.spec_from_file_location("base_screener", base_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    BaseScreener = module.BaseScreener
    test("BaseScreener 模块导入", True)

except Exception as e:
    test("BaseScreener 模块", False, str(e))
    all_passed = False

# Test 4: Screener Schemas
print_section("4. 筛选器 Schema 检查")
screener_names = ['er_ban_hui_tiao', 'ashare_21', 'jin_feng_huang',
                  'yin_feng_huang', 'zhang_ting_bei_liang_yin']

for name in screener_names:
    try:
        import importlib.util
        screener_file = workspace_root / 'screeners' / f'{name}_screener.py'
        spec = importlib.util.spec_from_file_location(f"{name}_screener", screener_file)
        module = importlib.util.module_from_spec(spec)

        # Set parent modules for relative imports to work
        sys.modules['screeners'] = type(sys)('screeners')
        sys.modules['screeners.base_screener'] = importlib.import_module('screeners.base_screener')

        spec.loader.exec_module(module)

        # Map name to class name
        class_name_map = {
            'er_ban_hui_tiao': 'ErBanHuiTiaoScreener',
            'ashare_21': 'AShare21Screener',
            'jin_feng_huang': 'JinFengHuangScreener',
            'yin_feng_huang': 'YinFengHuangScreener',
            'zhang_ting_bei_liang_yin': 'ZhangTingBeiLiangYinScreener'
        }
        class_name = class_name_map.get(name, ''.join(word.capitalize() for word in name.split('_')) + 'Screener')
        screener_class = getattr(module, class_name, None)

        if screener_class and hasattr(screener_class, 'get_parameter_schema'):
            schema = screener_class.get_parameter_schema()
            test(f"{name} Schema 定义", isinstance(schema, dict))
        else:
            test(f"{name} Schema 定义", False, "get_parameter_schema not found")
            all_passed = False

    except Exception as e:
        test(f"{name} Schema 定义", False, str(e))
        all_passed = False

# Summary
print_section("总结")
if all_passed:
    print(f"{GREEN}✓ 所有检查通过！{RESET}")
    print(f"\n可以安全启动服务：")
    print(f"  cd backend && python3 app.py --port 5003")
else:
    print(f"{RED}✗ 部分检查失败，请查看上面的错误信息{RESET}")

sys.exit(0 if all_passed else 1)
