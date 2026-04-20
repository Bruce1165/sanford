#!/usr/bin/env python3
"""
Screener Registry and Execution - Dynamic Discovery Version
"""
import os
import sys
import json
import subprocess
import re
from pathlib import Path
from datetime import datetime
import sqlite3
import pandas as pd
import inspect

# Add workspace to path
WORKSPACE_ROOT = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent)))
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

try:
    from models import (
        register_screener, get_all_screeners, create_run, complete_run,
        save_result, get_run, get_results, delete_screener
    )
except ImportError:
    from dashboard.models import (
        register_screener, get_all_screeners, create_run, complete_run,
        save_result, get_run, get_results, delete_screener
    )

try:
    from config_loader import load_screener_config
except ImportError:
    load_screener_config = None

DB_PATH = WORKSPACE_ROOT / "data" / "stock_data.db"


def is_valid_screener_file(filepath):
    """Check if a Python file is a valid screener"""
    if not filepath.is_file():
        return False
    
    if not filepath.suffix == '.py':
        return False
    
    # Must contain 'screener' in filename (case insensitive)
    if 'screener' not in filepath.name.lower():
        return False
    
    # Exclude base classes and test files
    exclude_patterns = ['base_', 'test_', '_test', '_base']
    filename_lower = filepath.name.lower()
    for pattern in exclude_patterns:
        if pattern in filename_lower:
            return False
    
    # Must contain a Screener class
    try:
        content = filepath.read_text(encoding='utf-8')
        # Look for class definition ending with 'Screener' (with or without parenthesis, allow version suffix like V2, V3, V4)
        if not re.search(r'class\s+\w+Screener(?:V?\d*)?\s*[\(:]', content):
            return False
        return True
    except Exception:
        return False


def extract_screener_info(filepath):
    """Extract screener info from Python file"""
    name = filepath.stem  # filename without extension
    display_name = name.replace('_', ' ').title()
    description = ""
    
    try:
        content = filepath.read_text(encoding='utf-8')
        
        # Extract docstring
        match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if match:
            docstring = match.group(1).strip()
            lines = [l.strip() for l in docstring.split('\n') if l.strip()]
            if lines:
                # First line is display name (remove ' - Screener' suffix if present)
                display_name = lines[0].split(' - ')[0].strip()
                if len(lines) > 1:
                    description = '\n'.join(lines[1:])
        
        # Extract class name (with optional version suffix like V2, V3, V4)
        class_match = re.search(r'class\s+(\w+Screener(?:V?\d*)?)\s*[\(:]', content)
        class_name = class_match.group(1) if class_match else name.title().replace('_', '')
        
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        class_name = name.title().replace('_', '')
    
    return {
        'name': name,
        'display_name': display_name,
        'description': description,
        'file_path': str(filepath),
        'class_name': class_name
    }


def discover_screeners():
    """Auto-discover all screeners from workspace root and scripts directory"""
    screeners = []
    
    # Scan both workspace root and scripts directory
    search_paths = [WORKSPACE_ROOT, WORKSPACE_ROOT / "scripts", WORKSPACE_ROOT / "screeners"]
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
        for filepath in search_path.iterdir():
            if is_valid_screener_file(filepath):
                screener_info = extract_screener_info(filepath)
                # 避免重复添加
                if not any(s['name'] == screener_info['name'] for s in screeners):
                    screeners.append(screener_info)
                    print(f"Discovered screener: {screener_info['name']} -> {screener_info['class_name']}")
    
    return screeners


def sync_screeners_with_db():
    """Sync discovered screeners with database (add new, remove deleted)"""
    discovered = discover_screeners()
    registered = get_all_screeners()
    registered_names = {s['name'] for s in registered}
    discovered_names = {s['name'] for s in discovered}
    
    # Add new screeners
    for s in discovered:
        if s['name'] not in registered_names:
            register_screener(
                name=s['name'],
                display_name=s['display_name'],
                description=s['description'],
                file_path=s['file_path']
            )
            print(f"Registered new screener: {s['name']}")
    
    # Remove deleted screeners
    for name in registered_names - discovered_names:
        delete_screener(name)
        print(f"Removed deleted screener: {name}")
    
    return discovered


def get_screener_class_name(screener_name):
    """Get class name from screener file dynamically"""
    # Try different file name patterns and directories
    possible_files = [
        WORKSPACE_ROOT / f"{screener_name}.py",
        WORKSPACE_ROOT / "scripts" / f"{screener_name}.py",
        WORKSPACE_ROOT / "screeners" / f"{screener_name}.py",
        WORKSPACE_ROOT / f"{screener_name}_screener.py",
        WORKSPACE_ROOT / "scripts" / f"{screener_name}_screener.py",
        WORKSPACE_ROOT / "screeners" / f"{screener_name}_screener.py",
    ]

    # Add additional patterns for coffee cup V4 and other screeners
    if screener_name == 'coffee_cup_v4':
        possible_files.extend([
            WORKSPACE_ROOT / "coffee_cup_handle_screener_v4.py",
            WORKSPACE_ROOT / "scripts" / "coffee_cup_handle_screener_v4.py",
            WORKSPACE_ROOT / "screeners" / "coffee_cup_handle_screener_v4.py",
        ])

    filepath = None
    for possible_file in possible_files:
        if possible_file.exists():
            filepath = possible_file
            break

    if not filepath:
        raise FileNotFoundError(f"Screener file not found: {screener_name}. Tried: {[str(f) for f in possible_files]}")
    
    try:
        content = filepath.read_text(encoding='utf-8')
        # Look for class definition ending with 'Screener' (with optional version suffix like V2, V3, V4)
        match = re.search(r'class\s+(\w+Screener(?:V?\d*)?)\s*[\(:]', content)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    
    # Fallback: convert filename to class name
    return screener_name.title().replace('_', '')


def run_screener_subprocess(screener_name, run_date):
    """Run screener in subprocess and capture results"""
    
    # Create run record
    run_id = create_run(screener_name, run_date)
    
    # Change to workspace root for correct DB path resolution
    original_cwd = os.getcwd()
    
    try:
        os.chdir(WORKSPACE_ROOT)
        
        # Import and run the screener directly
        # Try different file name patterns and directories
        possible_files = [
            WORKSPACE_ROOT / f"{screener_name}.py",
            WORKSPACE_ROOT / "scripts" / f"{screener_name}.py",
            WORKSPACE_ROOT / "screeners" / f"{screener_name}.py",
            WORKSPACE_ROOT / f"{screener_name}_screener.py",
            WORKSPACE_ROOT / "scripts" / f"{screener_name}_screener.py",
            WORKSPACE_ROOT / "screeners" / f"{screener_name}_screener.py",
        ]

        # Add additional patterns for coffee cup V4 and other screeners
        if screener_name == 'coffee_cup_v4':
            possible_files.extend([
                WORKSPACE_ROOT / "coffee_cup_handle_screener_v4.py",
                WORKSPACE_ROOT / "scripts" / "coffee_cup_handle_screener_v4.py",
                WORKSPACE_ROOT / "screeners" / "coffee_cup_handle_screener_v4.py",
            ])

        screener_file = None
        for possible_file in possible_files:
            if possible_file.exists():
                screener_file = possible_file
                break

        if not screener_file:
            raise FileNotFoundError(f"Screener file not found: {screener_name}. Tried: {[str(f) for f in possible_files]}")
        
        # Add workspace to path for imports
        if str(WORKSPACE_ROOT) not in sys.path:
            sys.path.insert(0, str(WORKSPACE_ROOT))
        if str(WORKSPACE_ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))
        if str(WORKSPACE_ROOT / "screeners") not in sys.path:
            sys.path.insert(0, str(WORKSPACE_ROOT / "screeners"))
        
        # Import the module — reload if already in sys.modules to pick up file changes
        import importlib.util as _ilu
        # If base_screener is stale (wrong __init__ signature), evict it so the
        # correct version from scripts/ is freshly imported.
        _bs = sys.modules.get('base_screener')
        if _bs is not None:
            try:
                import inspect as _insp
                sig = str(_insp.signature(_bs.BaseScreener.__init__))
                # Old signature has neither screener_name nor **kwargs
                if 'screener_name' not in sig and '**kwargs' not in sig:
                    del sys.modules['base_screener']
            except Exception:
                pass
        # (Re-)load the screener module fresh from its file path
        if screener_name in sys.modules:
            del sys.modules[screener_name]
        spec = _ilu.spec_from_file_location(screener_name, screener_file)
        module = _ilu.module_from_spec(spec)
        sys.modules[screener_name] = module   # register before exec to handle circular imports
        spec.loader.exec_module(module)
        
        # Get the screener class dynamically
        class_name = get_screener_class_name(screener_name)
        screener_class = getattr(module, class_name)
        
        # Instantiate and run — pass db_path and custom parameters if the class accepts them
        import inspect as _inspect
        _init_params = set(_inspect.signature(screener_class.__init__).parameters)
        _init_kwargs = {}
        if 'db_path' in _init_params:
            _init_kwargs['db_path'] = str(DB_PATH)

        # Load custom parameters from config file if available
        if load_screener_config:
            try:
                config = load_screener_config(screener_name)
                if config and 'parameters' in config:
                    # Map parameter names from config to __init__ parameter names
                    param_mapping = {
                        # Coffee cup V4 parameters
                        'RIM_INTERVAL_MIN': 'rim_interval_min',
                        'RIM_INTERVAL_MAX': 'rim_interval_max',
                        'RIM_PRICE_MATCH_PCT': 'rim_price_match_pct',
                        'CUP_DEPTH_MIN': 'cup_depth_min',
                        'CUP_DEPTH_MAX': 'cup_depth_max',
                        'RAPID_DECLINE_DAYS': 'rapid_decline_days',
                        'RAPID_ASCENT_DAYS': 'rapid_ascent_days',
                        'HANDLE_MAX_DAYS': 'handle_max_days',
                        'HANDLE_MAX_DROP_PCT': 'handle_max_drop_pct',
                        'AMOUNT_RATIO_THRESHOLD': 'amount_ratio_threshold',
                        'OSCILLATION_PRICE_CEIL_PCT': 'oscillation_price_ceil_pct',
                        # Lao Ya Tou Zhou Xian parameters (backward compatible)
                        'MA5_PERIOD': 'ma5_period',
                        'MA10_PERIOD': 'ma10_period',
                        'MA30_PERIOD': 'ma30_period',
                        'LOCAL_HIGH_WINDOW': 'local_high_window',
                        'VOLUME_CONTRACTION_THRESHOLD': 'volume_contraction_threshold',
                        'MIN_GAP': 'min_gap',
                        'MAX_GAP': 'max_gap',
                        'MIN_WEEKS': 'min_weeks',
                        'TEST_MODE': 'test_mode',
                        # Lao Ya Tou Zhou Xian amplitude parameters (applies to ALL signals)
                        'AMPLITUDE_LOOKBACK_WEEKS': 'amplitude_lookback_weeks',
                        'AMPLITUDE_MIN_THRESHOLD': 'amplitude_min_threshold',
                        # Lao Ya Tou Zhou Xian three-signal system parameters
                        'ENABLE_SIGNAL_1': 'enable_signal_1',
                        'ENABLE_SIGNAL_2': 'enable_signal_2',
                        'ENABLE_SIGNAL_3': 'enable_signal_3',
                        'SIGNAL_1_MIN_GAP': 'signal_1_min_gap',
                        'SIGNAL_1_VOLUME_RATIO_MIN': 'signal_1_volume_ratio_min',
                        'SIGNAL_2_CONFIRM_WEEKS': 'signal_2_confirm_weeks',
                        'SIGNAL_3_BREAKOUT_LOOKBACK': 'signal_3_breakout_lookback',
                        'POSITION_SIZE_SIGNAL_1_MIN': 'position_size_signal_1_min',
                        'POSITION_SIZE_SIGNAL_1_MAX': 'position_size_signal_1_max',
                        'POSITION_SIZE_SIGNAL_2_MIN': 'position_size_signal_2_min',
                        'POSITION_SIZE_SIGNAL_2_MAX': 'position_size_signal_2_max',
                        'POSITION_SIZE_SIGNAL_3_MIN': 'position_size_signal_3_min',
                        'POSITION_SIZE_SIGNAL_3_MAX': 'position_size_signal_3_max',
                        # Coffee cup parameters (legacy)
                        'MIN_DAYS_AFTER_BREAKOUT': 'min_days_after_breakout',
                        'MAX_DAYS_AFTER_BREAKOUT': 'max_days_after_breakout',
                        # Common pattern: UPPER_CASE in config -> snake_case in __init__
                    }
                    for config_key, param_name in param_mapping.items():
                        if config_key in config['parameters'] and param_name in _init_params:
                            _init_kwargs[param_name] = config['parameters'][config_key]['value']
            except Exception as e:
                print(f"Warning: Could not load config for {screener_name}: {e}")

        screener = screener_class(**_init_kwargs)
        results = screener.run_screening(run_date)
        

        if isinstance(results, tuple):
            # Extract results from tuple (results, analysis_data)
            results = results[0] if len(results) > 0 else []
        
        if isinstance(results, dict):
            # Flatten dict results (e.g., daily_hot_cold_screener)
            flat_results = []
            for key, items in results.items():
                if isinstance(items, list):
                    for item in items:
                        item['_category'] = key  # Mark category
                        flat_results.append(item)
            results = flat_results
        
        # Helper to convert NumPy types to Python types
        def convert_numpy(obj):
            if obj is None:
                return None
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(item) for item in obj]
            elif hasattr(obj, 'item'):  # NumPy scalar types (np.float64, np.int64, np.bool_, etc.)
                return obj.item()
            elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, dict)):
                # NumPy arrays
                return [convert_numpy(item) for item in obj]
            else:
                return obj

        # Convert NumPy types to Python types for JSON serialization
        json_results = convert_numpy(results) if results is not None else []

        # Save results to database
        for r in json_results:
            # 支持多种价格字段名（包括V4的latest_price）
            close_price = r.get('close') or r.get('current_price') or r.get('price') or r.get('latest_price') or 0
            # 支持多种代码和名称字段名（包括V4的stock_code和stock_name）
            stock_code = r.get('stock_code') or r.get('code') or ''
            stock_name = r.get('stock_name') or r.get('name') or ''
            # 排除已处理的字段，其余放入extra_data
            exclude_keys = ['stock_code', 'code', 'stock_name', 'name', 'close', 'current_price', 'price', 'latest_price', 'turnover', 'pct_change']
            extra_data = {k: v for k, v in r.items() if k not in exclude_keys}

            save_result(
                run_id=run_id,
                stock_code=stock_code,
                stock_name=stock_name,
                close_price=close_price,
                turnover=r.get('turnover', 0),
                pct_change=r.get('pct_change', 0),
                extra_data=extra_data
            )

        # Mark as completed
        complete_run(run_id, stocks_found=len(json_results))

        return {
            'success': True,
            'run_id': run_id,
            'stocks_found': len(json_results),
            'results': json_results
        }
        
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        complete_run(run_id, error_message=error_msg)
        
        return {
            'success': False,
            'run_id': run_id,
            'error': str(e),
            'traceback': traceback.format_exc()
        }
    finally:
        os.chdir(original_cwd)


def get_stock_data_for_chart(stock_code, days=60):
    """Get stock price data for K-line chart"""
    try:
        query = """
            SELECT trade_date, open, high, low, close, volume, amount
            FROM daily_prices
            WHERE code = ?
            ORDER BY trade_date DESC
            LIMIT ?
        """
        conn = sqlite3.connect(WORKSPACE_ROOT / "data" / "stock_data.db")
        df = pd.read_sql_query(query, conn, params=(stock_code, days))
        conn.close()
        
        if df.empty:
            return None
        
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # Convert to list of dicts for JSON serialization
        records = []
        for _, row in df.iterrows():
            records.append({
                'date': row['trade_date'].strftime('%Y-%m-%d'),
                'open': round(row['open'], 2),
                'high': round(row['high'], 2),
                'low': round(row['low'], 2),
                'close': round(row['close'], 2),
                'volume': int(row['volume']),
                'amount': round(row['amount'], 2) if pd.notna(row['amount']) else 0
            })
        
        return records
        
    except Exception as e:
        print(f"Error getting stock data for {stock_code}: {e}")
        return None


# CRUD Operations for Screeners/Cron Tasks/Manual Jobs

def create_screener_file(name, display_name, description, category, code_content=None):
    """Create a new screener/task file"""
    
    # Determine file location based on category
    if category == 'screener':
        filepath = WORKSPACE_ROOT / f"{name}.py"
    else:
        filepath = WORKSPACE_ROOT / "scripts" / f"{name}.py"
    
    if filepath.exists():
        raise FileExistsError(f"File already exists: {filepath}")
    
    # Generate default code if not provided
    if code_content is None:
        code_content = generate_default_screener_code(name, display_name, description, category)
    
    # Write file
    filepath.write_text(code_content, encoding='utf-8')
    
    # Register in database
    class_name = name.title().replace('_', '') + 'Screener'
    register_screener(
        name=name,
        display_name=display_name,
        description=description,
        file_path=str(filepath)
    )
    
    return {
        'name': name,
        'display_name': display_name,
        'description': description,
        'file_path': str(filepath),
        'class_name': class_name
    }

def update_screener_file(name, code_content, display_name=None, description=None):
    """Update an existing screener/task file"""
    
    # Find the file
    filepath = WORKSPACE_ROOT / f"{name}.py"
    if not filepath.exists():
        filepath = WORKSPACE_ROOT / "scripts" / f"{name}.py"
    
    if not filepath.exists():
        raise FileNotFoundError(f"Screener file not found: {name}")
    
    # Update code
    filepath.write_text(code_content, encoding='utf-8')
    
    # Update database if display_name or description provided
    if display_name or description:
        from models import update_screener
        update_screener(name, display_name=display_name, description=description)
    
    return {'success': True, 'name': name}

def delete_screener_file(name):
    """Delete a screener/task file"""
    
    # Find the file
    filepath = WORKSPACE_ROOT / f"{name}.py"
    if not filepath.exists():
        filepath = WORKSPACE_ROOT / "scripts" / f"{name}.py"
    
    # Delete file if exists
    if filepath.exists():
        filepath.unlink()
    
    # Remove from database
    delete_screener(name)
    
    return {'success': True, 'name': name}

def generate_default_screener_code(name, display_name, description, category):
    """Generate default screener code template"""
    
    class_name = name.title().replace('_', '') + 'Screener'
    
    if category == 'screener':
        template = f'''#!/usr/bin/env python3
"""
{display_name} - {description}
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

import pandas as pd


class {class_name}:
    """
    {display_name} - {description}
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        logger = logging.getLogger('{name}')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None):
        """
        运行筛选
        
        Returns:
            list: 筛选结果列表
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"开始运行 {display_name}: {{trade_date}}")
        
        # TODO: 实现筛选逻辑
        results = []
        
        self.logger.info(f"筛选完成: 找到 {{len(results)}} 只股票")
        return results


def main():
    """主函数"""
    screener = {class_name}()
    results = screener.run_screening()
    
    if results:
        print(f"\\n找到 {{len(results)}} 只股票:")
        for r in results[:5]:
            print(f"  {{r['code']}} {{r['name']}}")


if __name__ == '__main__':
    main()
'''
    elif category == 'cron':
        template = f'''#!/usr/bin/env python3
"""
{display_name} - {description}
Cron Task - 定时任务
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

import pandas as pd


class {class_name}:
    """
    {display_name} - Cron Task
    
    这是一个定时任务，在指定时间自动运行
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        logger = logging.getLogger('{name}')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None):
        """
        运行定时任务
        
        Returns:
            list: 任务结果列表
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"开始运行定时任务 {display_name}: {{trade_date}}")
        
        # TODO: 实现任务逻辑
        results = []
        
        self.logger.info(f"任务完成: 找到 {{len(results)}} 只股票")
        return results


def main():
    """主函数"""
    task = {class_name}()
    results = task.run_screening()
    
    if results:
        print(f"\\n找到 {{len(results)}} 只股票:")
        for r in results[:5]:
            print(f"  {{r['code']}} {{r['name']}}")


if __name__ == '__main__':
    main()
'''
    else:  # job
        template = f'''#!/usr/bin/env python3
"""
{display_name} - {description}
Manual Job - 手动任务
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

import pandas as pd


class {class_name}:
    """
    {display_name} - Manual Job
    
    这是一个手动触发的任务
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        logger = logging.getLogger('{name}')
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def run_screening(self, trade_date: str = None):
        """
        运行手动任务
        
        Returns:
            list: 任务结果列表
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        self.logger.info(f"开始运行手动任务 {display_name}: {{trade_date}}")
        
        # TODO: 实现任务逻辑
        results = []
        
        self.logger.info(f"任务完成: 找到 {{len(results)}} 只股票")
        return results


def main():
    """主函数"""
    job = {class_name}()
    results = job.run_screening()
    
    if results:
        print(f"\\n找到 {{len(results)}} 只股票:")
        for r in results[:5]:
            print(f"  {{r['code']}} {{r['name']}}")


if __name__ == '__main__':
    main()
'''
    
    return template


# Backward compatibility
register_discovered_screeners = sync_screeners_with_db

if __name__ == '__main__':
    # Test
    screeners = sync_screeners_with_db()
    print(f"\nTotal screeners: {len(screeners)}")
    for s in screeners:
        print(f"  - {s['name']}: {s['display_name']} ({s['class_name']})")
