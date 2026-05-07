#!/usr/bin/env python3
"""
Quick Verification Script - 快速验证系统功能

Purpose: 快速检查关键功能是否正常工作，确保没有回归
"""
import sys
import json
import sqlite3
import tempfile
from pathlib import Path

workspace_root = Path(__file__).parent.parent
script_dir = str(Path(__file__).parent)
sys.path = [p for p in sys.path if p != script_dir]
sys.path.insert(0, str(workspace_root))
backend_dir = str(workspace_root / 'backend')
sys.path = [p for p in sys.path if p != backend_dir]

def _ensure_screeners_package_wins():
    sys.path = [p for p in sys.path if p != backend_dir]
    if str(workspace_root) in sys.path:
        sys.path.remove(str(workspace_root))
    sys.path.insert(0, str(workspace_root))
    loaded_screeners = sys.modules.get('screeners')
    if loaded_screeners is not None:
        loaded_file = str(getattr(loaded_screeners, '__file__', '') or '')
        if loaded_file.endswith('/backend/screeners.py'):
            del sys.modules['screeners']


_ensure_screeners_package_wins()

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
test(f"配置文件数量正确 (15个)", len(config_files) == 15, f"found {len(config_files)} files")

for config_file in config_files:
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            if config_file.name == 'market_phase_profiles.json':
                test(
                    f"配置文件格式正确: {config_file.name}",
                    isinstance(config, dict) and 'profiles' in config
                )
            else:
                test(
                    f"配置文件格式正确: {config_file.name}",
                    isinstance(config, dict) and 'display_name' in config and 'parameters' in config
                )
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
    _ensure_screeners_package_wins()

    config = ConfigLoader.load_from_file('er_ban_hui_tiao')
    test("ConfigLoader 加载配置", config is not None)

except Exception as e:
    test("ConfigLoader 模块", False, str(e))
    all_passed = False

try:
    from backend.validators import validate_screener_config_update
    test("Validators 模块导入", True)
    _ensure_screeners_package_wins()

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
    _ensure_screeners_package_wins()
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
    from screeners.base_screener import BaseScreener
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
        import importlib
        module = importlib.import_module(f"screeners.{name}_screener")

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

# Test 5: Five Flags Readiness Regression
print_section("5. 五图筛查 Readiness 回归检查")
try:
    from backend.models import compute_five_flags_unprocessed_data_readiness

    def _mk_conn():
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('CREATE TABLE lao_ya_tou_pool (start_date TEXT, last_screened_date TEXT)')
        cur.execute('CREATE TABLE daily_prices (trade_date TEXT)')
        conn.commit()
        return conn

    # Case A: no pools
    conn = _mk_conn()
    out = compute_five_flags_unprocessed_data_readiness(conn)
    all_passed = test("A: 无股票池 -> no_pools", out.get('reason') == 'no_pools' and out.get('ready') is False) and all_passed
    conn.close()

    # Case B: pools exist but no price data
    conn = _mk_conn()
    conn.execute("INSERT INTO lao_ya_tou_pool(start_date,last_screened_date) VALUES(?,?)", ('2026-01-01', None))
    conn.commit()
    out = compute_five_flags_unprocessed_data_readiness(conn)
    all_passed = test("B: 无价格数据 -> no_price_data", out.get('reason') == 'no_price_data' and out.get('ready') is False) and all_passed
    conn.close()

    # Case C: future pools only -> ashare_not_updated
    conn = _mk_conn()
    conn.execute("INSERT INTO daily_prices(trade_date) VALUES(?)", ('2026-04-27',))
    conn.execute("INSERT INTO lao_ya_tou_pool(start_date,last_screened_date) VALUES(?,?)", ('2026-04-28', '2026-04-27'))
    conn.commit()
    out = compute_five_flags_unprocessed_data_readiness(conn)
    all_passed = test(
        "C: start_date 晚于 A股最新日期 -> ashare_not_updated",
        out.get('reason') == 'ashare_not_updated' and out.get('future_pool_count') == 1 and out.get('ready') is False
    ) and all_passed
    conn.close()

    # Case D: pending pools exist -> ready
    conn = _mk_conn()
    conn.execute("INSERT INTO daily_prices(trade_date) VALUES(?)", ('2026-04-27',))
    conn.execute("INSERT INTO lao_ya_tou_pool(start_date,last_screened_date) VALUES(?,?)", ('2026-04-01', '2026-04-24'))
    conn.commit()
    out = compute_five_flags_unprocessed_data_readiness(conn)
    all_passed = test(
        "D: 有待补筛股票池 -> ready",
        out.get('reason') == 'ready' and out.get('pending_pool_count') == 1 and out.get('ready') is True
    ) and all_passed
    conn.close()

    # Case E: up_to_date
    conn = _mk_conn()
    conn.execute("INSERT INTO daily_prices(trade_date) VALUES(?)", ('2026-04-27',))
    conn.execute("INSERT INTO lao_ya_tou_pool(start_date,last_screened_date) VALUES(?,?)", ('2026-04-01', '2026-04-27'))
    conn.commit()
    out = compute_five_flags_unprocessed_data_readiness(conn)
    all_passed = test(
        "E: 无需补筛 -> up_to_date",
        out.get('reason') == 'up_to_date' and out.get('pending_pool_count') == 0 and out.get('ready') is False
    ) and all_passed
    conn.close()

except Exception as e:
    test("五图 Readiness 回归检查", False, str(e))
    all_passed = False

# Test 6: Five Flags Progress Resume Regression
print_section("6. 五图筛查 Progress/断点续跑 回归检查")
try:
    import importlib.util
    script_file = workspace_root / 'scripts' / 'run_five_flags_pool_screening.py'
    spec = importlib.util.spec_from_file_location("run_five_flags_pool_screening", script_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    FiveFlagsPoolScreening = getattr(mod, 'FiveFlagsPoolScreening')

    db_path = str(workspace_root / 'data' / 'stock_data.db')
    if not Path(db_path).exists():
        raise FileNotFoundError(f"stock_data.db not found: {db_path}")

    pools = [{'id': 1}, {'id': 2}]

    def _run_with_progress(progress_payload, target_trade_date, flow_id):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=True) as fp:
            json.dump(progress_payload, fp, ensure_ascii=False, indent=2)
            fp.flush()

            s = FiveFlagsPoolScreening(db_path=db_path, progress_file=fp.name)
            s.target_trade_date = target_trade_date
            s.flow_id = flow_id

            captured = {'ids': None}

            def _fake_get_pools_to_screen(pool_ids=None):
                return list(pools)

            def _fake_process_pool_batch(in_pools):
                captured['ids'] = [p.get('id') for p in in_pools]
                return {
                    'total_stocks': len(in_pools),
                    'processed_stocks': 0,
                    'failed_stocks': 0,
                    'total_matches': 0,
                    'by_screener': {},
                    'level_duration_ms': {1: 0.0, 2: 0.0, 3: 0.0}
                }

            s.get_pools_to_screen = _fake_get_pools_to_screen
            s.process_pool_batch = _fake_process_pool_batch
            s.save_progress_file = lambda: None

            s.run_screening(pool_ids=None)
            return captured['ids']

    # Resume mode: same trade date + same flow + unfinished => filter processed_pool_ids
    ids = _run_with_progress(
        {
            'target_trade_date': '2026-04-27',
            'flow_id': 'five_flags_dag_v1',
            'total_stocks': 10,
            'processed_stocks': 3,
            'failed_stocks': 2,
            'processed_pool_ids': [1]
        },
        target_trade_date='2026-04-27',
        flow_id='five_flags_dag_v1'
    )
    all_passed = test("Resume: 同日未完成 -> 过滤已处理 pool_id", ids == [2]) and all_passed

    # New run: different trade date => do NOT filter by old processed_pool_ids
    ids = _run_with_progress(
        {
            'target_trade_date': '2026-04-26',
            'flow_id': 'five_flags_dag_v1',
            'total_stocks': 10,
            'processed_stocks': 10,
            'failed_stocks': 0,
            'processed_pool_ids': [1]
        },
        target_trade_date='2026-04-27',
        flow_id='five_flags_dag_v1'
    )
    all_passed = test("NewRun: 跨交易日 -> 不使用旧 processed_pool_ids", ids == [1, 2]) and all_passed

except Exception as e:
    test("五图 Progress/断点续跑 回归检查", False, str(e))
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
