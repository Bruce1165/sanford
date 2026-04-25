#!/usr/bin/env python3
"""
Flask Backend API for Trading Screener Dashboard
"""
import os
import sys
import json
import math
import uuid
import subprocess
import threading
import time
import smtplib
import ssl
from collections import deque
from pathlib import Path
from datetime import datetime, date, timedelta
from functools import wraps
from email.message import EmailMessage

from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from dotenv import load_dotenv

# Add dashboard to path
DASHBOARD_DIR = Path(__file__).parent
sys.path.insert(0, str(DASHBOARD_DIR))
sys.path.insert(0, str(DASHBOARD_DIR.parent))

# Load environment variables
env_file = Path('/Users/mac/NeoTrade2/config/.env')
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"[DEBUG] Loading .env from: {env_file}")
else:
    print(f"[WARNING] .env file not found at: {env_file}")

# Import models
from models import (
    init_db, get_db_connection, get_stock_db_connection, get_results_by_date,
    log_access, save_screener_config
)
from validators import validate_screener_config, validate_screener_config_update

# Import excel upload handler
from excel_upload import handle_excel_upload, handle_lao_ya_tou_pool_upload

# Import screeners module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "screeners_module", DASHBOARD_DIR / "screeners.py"
)
screeners_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screeners_module)
register_discovered_screeners = screeners_module.register_discovered_screeners
run_screener_subprocess = screeners_module.run_screener_subprocess


# Safe JSON encoder for NaN/Infinity handling
class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles NaN, Infinity, -Infinity by converting to null"""
    def encode(self, obj):
        obj = self._sanitize(obj)
        return super().encode(obj)

    def _sanitize(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(item) for item in obj]
        return obj


def safe_jsonify(data):
    """Return JSON response with NaN/Infinity handling"""
    return Response(
        json.dumps(data, cls=SafeJSONEncoder, ensure_ascii=False),
        mimetype='application/json'
    )


def _resolve_effective_trade_date(requested_date: str):
    """
    Resolve requested date to an effective trading day based on daily_prices.
    Returns tuple: (is_trading_day: bool, effective_trade_date: Optional[str])
    """
    conn = get_stock_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT MAX(trade_date) AS trade_date FROM daily_prices WHERE trade_date <= ?',
            (requested_date,),
        )
        row = cursor.fetchone()
        effective = None
        if row:
            effective = row['trade_date'] if isinstance(row, dict) else row[0]
        effective = str(effective)[:10] if effective else None
        return (effective == requested_date, effective)
    finally:
        conn.close()


def _normalize_schema_parameters(schema_obj):
    """Normalize schema object into flat parameter schema dict."""
    if not isinstance(schema_obj, dict):
        return {}
    params = schema_obj.get('parameters')
    if isinstance(params, dict):
        return params
    return schema_obj


def _extract_parameter_value(param_payload):
    """Extract scalar parameter value from either value-only or full object payload."""
    if isinstance(param_payload, dict) and 'value' in param_payload:
        return param_payload.get('value')
    return param_payload


def _extract_config_kwargs(config: object, init_params: dict) -> dict:
    """Extract accepted __init__ kwargs from config payload."""
    if not isinstance(config, dict):
        return {}

    kwargs = {}
    parameters = config.get('parameters')
    if isinstance(parameters, dict):
        for key, meta in parameters.items():
            normalized = str(key).strip().lower()
            if normalized in init_params:
                kwargs[normalized] = _extract_parameter_value(meta)

    config_json = config.get('config_json')
    if isinstance(config_json, dict):
        for key, value in config_json.items():
            normalized = str(key).strip().lower()
            if normalized in init_params:
                kwargs[normalized] = value

    if not kwargs:
        for key, value in config.items():
            if key in {'display_name', 'description', 'category', 'metadata', 'parameters'}:
                continue
            normalized = str(key).strip().lower()
            if normalized in init_params:
                kwargs[normalized] = value

    return kwargs


def _resolve_stock_name(stock_code: str) -> str:
    """Load stock name from stock database."""
    conn = get_stock_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM stocks WHERE code = ? LIMIT 1', (stock_code,))
    row = cursor.fetchone()
    conn.close()
    return (row['name'] if row and row['name'] else stock_code)


def _instantiate_screener(screener_name: str):
    """Instantiate screener class with db_path and dashboard config where available."""
    import inspect

    workspace_root = DASHBOARD_DIR.parent
    possible_files = [
        workspace_root / f"{screener_name}.py",
        workspace_root / "scripts" / f"{screener_name}.py",
        workspace_root / "screeners" / f"{screener_name}.py",
        workspace_root / f"{screener_name}_screener.py",
        workspace_root / "scripts" / f"{screener_name}_screener.py",
        workspace_root / "screeners" / f"{screener_name}_screener.py",
    ]

    if screener_name == 'coffee_cup_v4':
        possible_files.extend([
            workspace_root / "coffee_cup_handle_screener_v4.py",
            workspace_root / "scripts" / "coffee_cup_handle_screener_v4.py",
            workspace_root / "screeners" / "coffee_cup_handle_screener_v4.py",
        ])

    screener_file = next((f for f in possible_files if f.exists()), None)
    if not screener_file:
        raise FileNotFoundError(f"Screener file not found: {screener_name}")

    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))
    if str(workspace_root / "scripts") not in sys.path:
        sys.path.insert(0, str(workspace_root / "scripts"))
    if str(workspace_root / "screeners") not in sys.path:
        sys.path.insert(0, str(workspace_root / "screeners"))

    module_name = f"check_{screener_name}_module"
    if module_name in sys.modules:
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, screener_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    class_name = screeners_module.get_screener_class_name(screener_name)
    screener_class = getattr(module, class_name)
    init_params = inspect.signature(screener_class.__init__).parameters

    init_kwargs = {}
    if 'db_path' in init_params:
        init_kwargs['db_path'] = str(DASHBOARD_DIR.parent / 'data' / 'stock_data.db')

    try:
        from backend.config_loader import ConfigLoader
        config = ConfigLoader.load_config(screener_name, prefer_database=True)
        if config:
            init_kwargs.update(_extract_config_kwargs(config, init_params))
    except Exception:
        pass

    if 'enable_news' in init_params:
        init_kwargs['enable_news'] = False
    if 'enable_llm' in init_params:
        init_kwargs['enable_llm'] = False
    if 'enable_progress' in init_params:
        init_kwargs['enable_progress'] = False
    if 'use_pool' in init_params:
        init_kwargs['use_pool'] = False

    return screener_class(**init_kwargs)


def _normalize_check_response(raw_result: object, screener_name: str, stock_code: str, stock_name: str, check_date: str) -> dict:
    """Normalize various screener result formats to frontend check card schema."""
    if raw_result is None:
        return {
            'match': False,
            'code': stock_code,
            'name': stock_name,
            'date': check_date,
            'details': {},
            'reasons': [f'未命中 {screener_name} 条件'],
        }

    if not isinstance(raw_result, dict):
        return {
            'match': False,
            'code': stock_code,
            'name': stock_name,
            'date': check_date,
            'details': {},
            'reasons': [f'无效返回格式: {type(raw_result).__name__}'],
        }

    match = raw_result.get('match')
    if match is None:
        match = raw_result.get('matched')
    if match is None:
        match = raw_result.get('pattern_found')
    match = _to_native_bool(match)

    details = raw_result.get('details')
    if not isinstance(details, dict):
        details = {}

    if not details and match:
        reserved = {
            'match', 'matched', 'pattern_found',
            'code', 'stock_code', 'name', 'stock_name',
            'date', 'reason', 'reason_hit', 'reason_miss', 'reasons', 'error'
        }
        details = {k: v for k, v in raw_result.items() if k not in reserved}

    reasons = raw_result.get('reasons')
    if not isinstance(reasons, list):
        reasons = []
    if not match and not reasons:
        reason_miss = raw_result.get('reason_miss')
        reason = raw_result.get('reason')
        error = raw_result.get('error')
        if isinstance(reason_miss, str) and reason_miss.strip():
            reasons = [reason_miss]
        elif isinstance(reason, str) and reason.strip():
            reasons = [reason]
        elif isinstance(error, str) and error.strip():
            reasons = [error]
        else:
            reasons = [f'未命中 {screener_name} 条件']

    return {
        'match': match,
        'code': raw_result.get('code') or raw_result.get('stock_code') or stock_code,
        'name': raw_result.get('name') or raw_result.get('stock_name') or stock_name,
        'date': raw_result.get('date') or check_date,
        'details': details,
        'reasons': reasons,
    }


FIVE_FLAGS_TIMELINE_SCREENERS = [
    {
        'screener_id': 'shi_pan_xian',
        'label': '试盘线',
        'aliases': ['试盘线', '涨停试盘线', 'shi_pan_xian', 'shipanxian', 'test_line'],
    },
    {
        'screener_id': 'jin_feng_huang',
        'label': '金凤凰',
        'aliases': ['金凤凰', '涨停金凤凰', 'jin_feng_huang', 'jinfenghuang', 'golden_phoenix'],
    },
    {
        'screener_id': 'yin_feng_huang',
        'label': '银凤凰',
        'aliases': ['银凤凰', '涨停银凤凰', 'yin_feng_huang', 'yinfenghuang', 'silver_phoenix'],
    },
    {
        'screener_id': 'zhang_ting_bei_liang_yin',
        'label': '倍量阴',
        'aliases': ['倍量阴', '涨停倍量阴', 'zhang_ting_bei_liang_yin', 'beiliangyin', 'double_volume_bear'],
    },
    {
        'screener_id': 'er_ban_hui_tiao',
        'label': '二板回调',
        'aliases': ['二板回调', 'er_ban_hui_tiao', 'erbanhuitiao', 'second_board_pullback'],
    },
]


def _normalize_screener_token(value):
    return str(value or '').strip().lower().replace(' ', '').replace('-', '').replace('_', '')


def _resolve_five_flags_screener_id(value):
    source = _normalize_screener_token(value)
    for item in FIVE_FLAGS_TIMELINE_SCREENERS:
        for alias in item['aliases']:
            if _normalize_screener_token(alias) == source:
                return item['screener_id']
    return None


def _parse_bool_arg(name: str, default: bool = False) -> bool:
    value = request.args.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _iter_dates(start_date: str, end_date: str):
    cursor = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    while cursor <= end:
        yield cursor.strftime('%Y-%m-%d')
        cursor += timedelta(days=1)


def _to_native_bool(value) -> bool:
    """Convert numpy/pandas bool-like values to native Python bool."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    item = getattr(value, 'item', None)
    if callable(item):
        try:
            value = item()
        except Exception:
            pass
    return bool(value)


def _normalize_failed_check(check):
    """Normalize one failed-check object into JSON-safe primitives."""
    if not isinstance(check, dict):
        return None
    return {
        'key': str(check.get('key', '') or ''),
        'label': str(check.get('label', '') or ''),
        'passed': _to_native_bool(check.get('passed')),
        'message': str(check.get('message', '') or ''),
    }


def _normalize_failed_checks(items):
    """Normalize failed-check list into JSON-safe list."""
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        check = _normalize_failed_check(item)
        if check is not None:
            normalized.append(check)
    return normalized


def _normalize_text_list(items, limit: int = 10):
    """Normalize free-text list into deduplicated JSON-safe strings."""
    if not isinstance(items, list):
        return []
    result = []
    seen = set()
    for item in items:
        text = str(item or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


# Authentication
DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')
if not DASHBOARD_PASSWORD:
    raise ValueError("DASHBOARD_PASSWORD environment variable is required")


def check_auth(_username, password):
    """验证密码（只验证密码）"""
    return password == DASHBOARD_PASSWORD


def authenticate():
    """返回 401 响应要求认证"""
    return Response(
        'Please enter password to access Dashboard',
        401,
        {'WWW-Authenticate': 'Basic realm="NeoTrade Dashboard"'}
    )


def require_auth(f):
    """装饰器：要求认证"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


# Initialize Flask app
app = Flask(__name__, static_folder=None)


# CORS configuration
CORS_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:3000',
    'https://neotrade.vip.cpolar.cn',
    'https://neotrade.cpolar.cn',
    'https://neiltrade.cloud',
]
CORS(app, origins=CORS_ORIGINS, supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'])


# Before request handler
@app.before_request
def before_request():
    # Health check不需要认证
    if request.path == '/api/health':
        return None

    # Local IPs skip auth
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    local_ips = ['127.0.0.1', '::1', 'localhost']
    is_local = (ip in local_ips or
                ip.startswith('192.168.') or
                ip.startswith('10.') or
                any(ip.startswith(f'172.{x}.') for x in range(16, 32)))

    # Log access for main pages
    if request.path == '/' or (not request.path.startswith('/api/') and
                               not request.path.startswith('/assets/')):
        try:
            log_access(ip, request.user_agent.string, request.path)
        except:
            pass

    # Non-local requests need auth
    if not is_local:
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()


# Static routes
@app.route('/')
def index():
    response = send_from_directory(
        DASHBOARD_DIR.parent / 'frontend/dist', 'index.html'
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    response = send_from_directory(
        DASHBOARD_DIR.parent / 'frontend/dist/assets', filename
    )
    # Vite assets are content-hashed; enable long-term immutable caching.
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


@app.route('/<path:path>')
def catch_all(path):
    # Do not swallow API requests with SPA index fallback.
    if path.startswith('api/'):
        return jsonify({'error': f'API not found: /{path}'}), 404
    response = send_from_directory(
        DASHBOARD_DIR.parent / 'frontend/dist', 'index.html'
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


# API Routes
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/screeners')
def get_screeners_list():
    """Get all screeners list grouped by category"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get screeners with categories from screener_configs
    cursor.execute(
        'SELECT screener_name, display_name, description, category, config_json, config_schema, current_version, created_at, updated_at '
        'FROM screener_configs ORDER BY category, screener_name'
    )
    rows = cursor.fetchall()
    conn.close()

    screeners = []
    for row in rows:
        (screener_name, display_name, description, category, config_json, config_schema, version, created_at, updated_at) = row
        screeners.append({
            'name': screener_name,
            'display_name': display_name,
            'description': description,
            'category': category,
            'config': json.loads(config_json) if config_json else None,
            'config_schema': json.loads(config_schema) if config_schema else None,
            'version': version,
            'created_at': created_at,
            'updated_at': updated_at
        })

    return safe_jsonify({'screeners': screeners})


@app.route('/api/results')
def get_screener_results():
    """Get screener results"""
    screener_name = request.args.get('screener')
    run_date = request.args.get('date') or date.today().isoformat()

    try:
        datetime.strptime(run_date, '%Y-%m-%d')
    except ValueError:
        return safe_jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    is_td, effective = _resolve_effective_trade_date(run_date)
    if not is_td:
        return safe_jsonify({
            'error': 'Non-trading day',
            'requested_date': run_date,
            'effective_trade_date': effective,
        }), 400

    if not screener_name:
        return safe_jsonify({'error': 'Missing screener parameter'}), 400

    results = get_results_by_date(screener_name, run_date)

    return safe_jsonify(results)


@app.route('/api/stock/<stock_code>/chart')
def get_stock_chart(stock_code):
    """Get chart (K-line) data for a stock."""
    code = (stock_code or '').strip()
    if len(code) != 6 or not code.isdigit():
        return jsonify({'error': 'Invalid stock code, use 6 digits'}), 400

    raw_days = request.args.get('days', '60')
    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        return jsonify({'error': 'days must be an integer'}), 400
    days = max(5, min(days, 400))

    chart_data = screeners_module.get_stock_data_for_chart(code, days=days)
    if not chart_data:
        return safe_jsonify({'stock_code': code, 'days': days, 'data': []})

    return safe_jsonify({'stock_code': code, 'days': days, 'data': chart_data})


@app.route('/api/check-stock', methods=['POST'])
def check_stock():
    """Ad-hoc check if a stock matches one screener on a date."""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    payload = request.get_json() or {}
    screener_name = (payload.get('screener') or '').strip()
    stock_code = (payload.get('code') or '').strip()
    check_date = (payload.get('date') or date.today().isoformat()).strip()

    if not screener_name:
        return jsonify({'error': 'Missing screener parameter'}), 400
    if not stock_code:
        return jsonify({'error': 'Missing code parameter'}), 400
    if len(stock_code) != 6 or not stock_code.isdigit():
        return jsonify({'error': 'Invalid stock code, use 6 digits'}), 400
    try:
        datetime.strptime(check_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    try:
        stock_name = _resolve_stock_name(stock_code)

        # Five-flags screeners: use adapter for unified "miss diagnostics" output.
        if _resolve_five_flags_screener_id(screener_name):
            from scripts.pool_screener_adapter import ScreenerAdapter

            adapter = ScreenerAdapter(db_path=str(DASHBOARD_DIR.parent / 'data' / 'stock_data.db'))
            adapter_result = adapter.check_stock(
                screener_id=_resolve_five_flags_screener_id(screener_name),
                stock_code=stock_code,
                stock_name=stock_name,
                date=check_date,
                include_miss_details=True
            )
            return safe_jsonify(_normalize_check_response(adapter_result, screener_name, stock_code, stock_name, check_date))

        screener = _instantiate_screener(screener_name)

        if hasattr(screener, 'current_date'):
            screener.current_date = check_date
        if hasattr(screener, '_current_date'):
            try:
                screener._current_date = datetime.strptime(check_date, '%Y-%m-%d').date()
            except Exception:
                pass

        raw_result = None
        if hasattr(screener, 'check_single_stock'):
            try:
                raw_result = screener.check_single_stock(stock_code, check_date)
            except Exception as check_exc:
                # Some legacy check_single_stock implementations rely on missing globals.
                # Fallback to screen_stock to keep CHECK endpoint available.
                if hasattr(screener, 'screen_stock'):
                    screen_result = screener.screen_stock(stock_code, stock_name)
                    if isinstance(screen_result, dict):
                        raw_result = {
                            'match': True,
                            'code': stock_code,
                            'name': stock_name,
                            'date': check_date,
                            'details': screen_result,
                            'reasons': [],
                        }
                    else:
                        raw_result = {
                            'match': False,
                            'code': stock_code,
                            'name': stock_name,
                            'date': check_date,
                            'details': {},
                            'reasons': [f'未命中 {screener_name} 条件'],
                        }
                else:
                    raw_result = {
                        'match': False,
                        'code': stock_code,
                        'name': stock_name,
                        'date': check_date,
                        'details': {},
                        'reasons': [f'检查失败: {str(check_exc)}'],
                    }
        elif hasattr(screener, 'screen_stock'):
            screen_result = screener.screen_stock(stock_code, stock_name)
            if isinstance(screen_result, dict):
                raw_result = {
                    'match': True,
                    'code': stock_code,
                    'name': stock_name,
                    'date': check_date,
                    'details': screen_result,
                    'reasons': [],
                }
            else:
                raw_result = {
                    'match': False,
                    'code': stock_code,
                    'name': stock_name,
                    'date': check_date,
                    'details': {},
                    'reasons': [f'未命中 {screener_name} 条件'],
                }
        else:
            return jsonify({'error': f'Screener {screener_name} does not support stock checking'}), 400

        return safe_jsonify(_normalize_check_response(raw_result, screener_name, stock_code, stock_name, check_date))
    except FileNotFoundError:
        return jsonify({'error': f'Screener not found: {screener_name}'}), 404
    except Exception as e:
        return jsonify({'error': f'check failed: {str(e)}'}), 500


@app.route('/api/screeners/<screener_name>/run', methods=['POST'])
def run_screener(screener_name):
    """Run a screener"""
    try:
        # Get run_date from request body
        request_data = request.get_json() or {}
        run_date = request_data.get('date')

        if not run_date:
            return safe_jsonify({'error': 'Missing date parameter'}), 400

        # Validate date format
        try:
            datetime.strptime(run_date, '%Y-%m-%d')
        except ValueError:
            return safe_jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

        is_td, effective = _resolve_effective_trade_date(run_date)
        if not is_td:
            return safe_jsonify({
                'error': 'Non-trading day',
                'requested_date': run_date,
                'effective_trade_date': effective,
            }), 400

        # Call the actual screener run function
        run_id = run_screener_subprocess(screener_name, run_date)

        return safe_jsonify({
            'status': 'success',
            'screener': screener_name,
            'run_id': run_id,
            'requested_date': run_date,
            'effective_trade_date': run_date
        })

    except FileNotFoundError as e:
        return safe_jsonify({'error': str(e)}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return safe_jsonify({'error': str(e)}), 500


@app.route('/api/screeners/<screener_name>/config', methods=['GET'])
def get_screener_config(screener_name):
    """Get screener configuration"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get config and schema from database
    cursor.execute(
        'SELECT display_name, description, category, config_json, config_schema, current_version, created_at, updated_at '
        'FROM screener_configs WHERE screener_name = ?',
        (screener_name,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Screener not found'}), 404

    (display_name, description, category, config_json, schema_json, version, created_at, updated_at) = row
    config = json.loads(config_json) if config_json else {'parameters': {}}
    schema = json.loads(schema_json) if schema_json else {}
    schema_parameters = _normalize_schema_parameters(schema)

    # Merge config with schema for full parameter details
    merged_config = {
        'display_name': display_name,
        'description': description,
        'category': category,
        'version': version,
        'created_at': created_at,
        'updated_at': updated_at,
        'parameters': {}
    }

    # Load fallback schema from JSON config file if database schema is empty
    if not schema_parameters:
        config_file_path = DASHBOARD_DIR.parent / 'config' / 'screeners' / f'{screener_name}.json'
        if config_file_path.exists():
            try:
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # Use parameters from file as schema
                    schema_parameters = file_config.get('parameters', {})
                    print(f"[DEBUG] Loaded schema from config file: {len(schema_parameters)} parameters")
            except Exception as e:
                print(f"[DEBUG] Failed to load config file: {e}")

    # Build parameters with schema metadata (fallback to config if schema is empty)
    if schema_parameters:
        for param_name, param_config in schema_parameters.items():
            param_data = param_config.copy()
            # Override value with current config value if exists
            if param_name in config.get('parameters', {}):
                config_value = config['parameters'][param_name]
                # Handle both value-only and full param structure
                if isinstance(config_value, dict):
                    param_data['value'] = config_value.get('value', param_config.get('default'))
                else:
                    param_data['value'] = config_value
            else:
                param_data['value'] = param_config.get('default')
            merged_config['parameters'][param_name] = param_data
    elif config.get('parameters'):
        # Fallback: use config parameters directly
        for param_name, param_data in config['parameters'].items():
            merged_config['parameters'][param_name] = param_data

    return safe_jsonify(merged_config)


@app.route('/api/screeners/<screener_name>/config', methods=['PUT'])
def update_screener_config(screener_name):
    """Update screener configuration"""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    config_data = request.get_json() or {}
    is_valid_update, update_error, validated_update = validate_screener_config_update(config_data)
    if not is_valid_update:
        return jsonify({'error': update_error}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get existing config
    cursor.execute(
        'SELECT display_name, description, category, config_json, config_schema, current_version '
        'FROM screener_configs WHERE screener_name = ?',
        (screener_name,)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'Screener not found'}), 404

    display_name, description, category, config_json, schema_json, current_version = row
    schema = json.loads(schema_json) if schema_json else {}
    schema_parameters = _normalize_schema_parameters(schema)
    # Fallback to file schema if database schema is missing
    if not schema_parameters:
        config_file_path = DASHBOARD_DIR.parent / 'config' / 'screeners' / f'{screener_name}.json'
        if config_file_path.exists():
            try:
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    schema_parameters = file_config.get('parameters', {})
                    schema = {'parameters': schema_parameters}
            except Exception as e:
                print(f"[DEBUG] Failed to load fallback schema file for update: {e}")

    existing_config = json.loads(config_json) if config_json else {'parameters': {}}
    conn.close()

    incoming_parameters = validated_update.get('parameters', {})
    if not isinstance(incoming_parameters, dict):
        return jsonify({'error': 'Parameters must be an object'}), 400

    normalized_values = {
        param_name: _extract_parameter_value(param_payload)
        for param_name, param_payload in incoming_parameters.items()
    }

    is_valid_config, validation_errors = validate_screener_config(
        {
            'display_name': display_name,
            'parameters': normalized_values
        },
        schema_parameters
    )
    if not is_valid_config:
        return jsonify({
            'error': '参数校验失败',
            'validation_errors': validation_errors
        }), 400

    # Merge new config with existing parameters
    merged_config = {
        'display_name': validated_update.get('display_name', display_name),
        'description': validated_update.get('description', description),
        'category': validated_update.get('category', category),
        'parameters': existing_config.get('parameters', {}).copy()
    }

    # Update parameters from request
    for param_name, param_value in normalized_values.items():
        if schema_parameters and param_name in schema_parameters:
            # Use schema metadata and always keep scalar value in "value"
            param_schema = schema_parameters[param_name]
            merged_config['parameters'][param_name] = {
                'value': param_value,
                'display_name': param_schema.get('display_name', param_name),
                'description': param_schema.get('description', ''),
                'group': param_schema.get('group', '其他'),
                'type': param_schema.get('type', 'string'),
                'min': param_schema.get('min'),
                'max': param_schema.get('max'),
                'step': param_schema.get('step'),
                'default': param_schema.get('default')
            }
        else:
            # No schema available: preserve prior metadata if exists
            existing_param = merged_config['parameters'].get(param_name, {})
            if isinstance(existing_param, dict):
                merged_config['parameters'][param_name] = {
                    'value': param_value,
                    'display_name': existing_param.get('display_name', param_name),
                    'description': existing_param.get('description', ''),
                    'group': existing_param.get('group', '其他'),
                    'type': existing_param.get('type', 'string'),
                    'min': existing_param.get('min'),
                    'max': existing_param.get('max'),
                    'step': existing_param.get('step'),
                    'default': existing_param.get('default')
                }
            else:
                merged_config['parameters'][param_name] = {
                    'value': param_value,
                    'display_name': param_name,
                    'description': '',
                    'group': '其他',
                    'type': 'string'
                }

    # Ensure schema is saved in normalized shape
    schema_to_save = schema
    if schema_parameters and not (isinstance(schema_to_save, dict) and isinstance(schema_to_save.get('parameters'), dict)):
        schema_to_save = {'parameters': schema_parameters}

    new_version = save_screener_config(
        screener_name=screener_name,
        config=merged_config,
        schema=schema_to_save,
        change_summary=validated_update.get('change_summary', '配置更新'),
        changed_by=validated_update.get('updated_by', 'system')
    )

    merged_config['metadata'] = {
        'version': new_version,
        'updated_by': validated_update.get('updated_by', 'system')
    }
    return jsonify({
        'status': 'success',
        'config': merged_config,
        'version': new_version,
        'previous_version': current_version
    })
@app.route('/api/calendar')
def get_trading_calendar():
    """Get trading calendar"""
    # Placeholder - implement with actual trading calendar logic
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get available dates from results
    cursor.execute(
        'SELECT DISTINCT run_date FROM screener_runs '
        'ORDER BY run_date DESC LIMIT 30'
    )
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()

    return jsonify({'dates': dates})


@app.route('/api/trading-day')
def is_trading_day():
    qdate = (request.args.get('date') or '').strip()
    if not qdate:
        qdate = date.today().isoformat()

    try:
        datetime.strptime(qdate, '%Y-%m-%d')
    except ValueError:
        return safe_jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    is_td, effective = _resolve_effective_trade_date(qdate)
    return safe_jsonify({'date': qdate, 'is_trading_day': is_td, 'recent_trading_day': effective})


@app.route('/api/data-health')
def data_health():
    """Get data health status for stock database"""
    # Check stock data database
    stock_db_path = DASHBOARD_DIR.parent / 'data' / 'stock_data.db'
    stock_db_exists = stock_db_path.exists()

    if not stock_db_exists:
        return jsonify({
            'db_health': {
                'timestamp': None,
                'status': 'critical',
                'checks': {
                    'stock_pool': {'active_stocks': 0, 'delisted_stocks': 0, 'newly_listed_30d': 0, 'st_stocks': 0},
                    'today_data': {'date': None, 'total_stocks': 0, 'normal_trading': 0, 'suspended': 0},
                    'history_data': {'earliest_date': None, 'latest_date': None, 'trading_days': 0, 'total_records': 0, 'missing_price_records': 0},
                    'macro_data': {'total_market_cap': {'pct': 0}, 'pe_ratio': {'pct': 0}, 'pb_ratio': {'pct': 0}, 'sector': {'pct': 0}, 'ifind_updated_at': None}
                }
            },
            'run_history': []
        })

    conn = get_stock_db_connection()
    cursor = conn.cursor()

    # Debug: print database path
    db_path = conn.execute('PRAGMA database_list').fetchall()[0][2]
    print(f'[DEBUG] Connected to database: {db_path}')

    # Stock Pool stats
    cursor.execute('SELECT COUNT(*) FROM stocks WHERE is_delisted = 0')
    result = cursor.fetchone()
    active_stocks = result[0] if result else 0
    print(f'[DEBUG] Active stocks: {active_stocks}')

    cursor.execute('SELECT COUNT(*) FROM stocks WHERE is_delisted = 1')
    result = cursor.fetchone()
    delisted_stocks = result[0] if result else 0

    # Newly listed in 30 days
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE list_date >= date('now', '-30 days')")
    result = cursor.fetchone()
    newly_listed_30d = result[0] if result else 0

    # ST stocks
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE code LIKE '%ST%' OR name LIKE '%ST%'")
    result = cursor.fetchone()
    st_stocks = result[0] if result else 0

    # Today data
    today = date.today().isoformat()
    cursor.execute('''
        SELECT COUNT(DISTINCT code), COUNT(*)
        FROM daily_prices WHERE trade_date = ?
    ''', (today,))
    today_result = cursor.fetchone()
    if today_result:
        today_stocks = today_result[0]
        today_records = today_result[1]
    else:
        today_stocks = 0
        today_records = 0

    # Normal trading (not suspended - check if volume > 0)
    cursor.execute('''
        SELECT COUNT(DISTINCT code)
        FROM daily_prices WHERE trade_date = ? AND volume > 0
    ''', (today,))
    result = cursor.fetchone()
    normal_trading = result[0] if result else 0

    suspended = today_stocks - normal_trading

    # History data
    cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices')
    history_dates = cursor.fetchone()
    earliest_date = history_dates[0] if history_dates and history_dates[0] else None
    latest_date = history_dates[1] if history_dates and history_dates[1] else None

    cursor.execute('SELECT COUNT(DISTINCT trade_date) FROM daily_prices')
    result = cursor.fetchone()
    trading_days = result[0] if result else 0

    cursor.execute('SELECT COUNT(*) FROM daily_prices')
    result = cursor.fetchone()
    total_records = result[0] if result else 0

    # Missing records (should be trading_days * active_stocks - total_records)
    if trading_days and active_stocks:
        expected_records = trading_days * active_stocks
        missing_price_records = max(0, expected_records - total_records)
    else:
        missing_price_records = 0

    # Macro data coverage (from stocks table)
    cursor.execute('SELECT COUNT(*) FROM stocks WHERE total_market_cap > 0')
    result = cursor.fetchone()
    market_cap_records = result[0] if result else 0

    cursor.execute('SELECT COUNT(*) FROM stocks WHERE pe_ratio > 0')
    result = cursor.fetchone()
    pe_records = result[0] if result else 0

    cursor.execute('SELECT COUNT(*) FROM stocks WHERE pb_ratio > 0')
    result = cursor.fetchone()
    pb_records = result[0] if result else 0

    cursor.execute('SELECT COUNT(*) FROM stock_meta WHERE sector_lv1 IS NOT NULL AND sector_lv1 != ""')
    result = cursor.fetchone()
    sector_records = result[0] if result else 0

    if active_stocks > 0:
        market_cap_pct = (market_cap_records / active_stocks) * 100
        pe_pct = (pe_records / active_stocks) * 100
        pb_pct = (pb_records / active_stocks) * 100
        sector_pct = (sector_records / active_stocks) * 100
    else:
        market_cap_pct = pe_pct = pb_pct = sector_pct = 0

    conn.close()

    # Determine health status based on data freshness
    status = 'healthy'
    if not latest_date:
        status = 'critical'
    else:
        try:
            latest_dt = datetime.strptime(latest_date, '%Y-%m-%d').date()
            days_ago = (date.today() - latest_dt).days
            if days_ago > 1:
                status = 'warning'
            if days_ago > 3:
                status = 'critical'
        except:
            status = 'warning'

    return jsonify({
        'db_health': {
            'timestamp': datetime.now().isoformat(),
            'status': status,
            'checks': {
                'stock_pool': {
                    'active_stocks': active_stocks,
                    'delisted_stocks': delisted_stocks,
                    'newly_listed_30d': newly_listed_30d,
                    'st_stocks': st_stocks
                },
                'today_data': {
                    'date': today if today_stocks > 0 else None,
                    'total_stocks': today_stocks,
                    'total': today_records,
                    'normal_trading': normal_trading,
                    'normal_stocks': normal_trading,
                    'suspended': suspended
                },
                'history_data': {
                    'earliest_date': earliest_date,
                    'latest_date': latest_date,
                    'trading_days': trading_days,
                    'total_records': total_records,
                    'missing_price_records': missing_price_records
                },
                'macro_data': {
                    'total_market_cap': {'pct': round(market_cap_pct, 1)},
                    'pe_ratio': {'pct': round(pe_pct, 1)},
                    'pb_ratio': {'pct': round(pb_pct, 1)},
                    'sector': {'pct': round(sector_pct, 1)},
                    'ifind_updated_at': latest_date  # Using latest date as proxy
                }
            }
        },
        'run_history': []
    })


@app.route('/api/data-health/upload', methods=['POST'])
def upload_stock_data():
    """Upload and process Excel file with stock data"""
    import tempfile
    import os
    import logging
    logger = logging.getLogger(__name__)

    # Check if file is in request
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Get force_update option
    force_update = request.form.get('force_update', 'false').lower() == 'true'

    # Debug: log file info
    logger.info(f"Upload request: filename={file.filename}, force_update={force_update}, size={file.content_length}")

    # Save uploaded file to temp location
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        file.save(temp_path)
        logger.info(f"File saved to: {temp_path}, size={os.path.getsize(temp_path)} bytes")

        # Debug: show first few bytes of file to detect encoding issues
        try:
            with open(temp_path, 'rb') as f:
                first_bytes = f.read(500)
                logger.info(f"First 500 bytes (hex): {first_bytes.hex()[:200]}...")
                logger.info(f"First 500 bytes (text attempt): {first_bytes.decode('utf-8', errors='replace')[:300]}...")
                # Try to detect if file has BOM or special markers
                if first_bytes.startswith(b'\xef\xbb\xbf'):
                    logger.info("File has UTF-8 BOM")
                elif first_bytes.startswith(b'\xff\xfe'):
                    logger.info("File has UTF-16 LE BOM")
                elif first_bytes.startswith(b'\xfe\xff'):
                    logger.info("File has UTF-16 BE BOM")
        except Exception as debug_e:
            logger.info(f"Debug read failed: {debug_e}")

        # Process the upload
        result = handle_excel_upload(temp_path, force_update=force_update)
        logger.info(f"Upload result: {result['status']}, message={result.get('message', '')}")

        # Clean up temp file
        os.remove(temp_path)
        os.rmdir(temp_dir)

        if result['status'] in ['success', 'warning']:
            return safe_jsonify({
                'success': True,
                'message': result['message'],
                'trade_date': result['trade_date'],
                'daily_prices': result['daily_prices'],
                'stock_metadata': result['stock_metadata'],
                'warnings': result.get('warnings', [])
            })
        else:
            return jsonify({'success': False, 'error': result['message']}), 400

    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

        logger.error(f"Upload failed: {e}")
        return jsonify({'success': False, 'error': f"上传失败: {str(e)}"}), 500


# Initialize database
print('[DEBUG] Initializing database...')
init_db()
print('[DEBUG] Registering screeners...')
register_discovered_screeners()

# Load screener configurations from config/screeners/*.json
print('[DEBUG] Loading screener configurations...')
config_dir = DASHBOARD_DIR.parent / 'config' / 'screeners'
if config_dir.exists():
    config_files = sorted(config_dir.glob('*.json'))

    conn = get_db_connection()
    cursor = conn.cursor()

    for config_file in config_files:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            screener_name = config_file.stem  # filename without .json

            # Extract category and display_name from config
            category = config_data.get('category', '未分类')
            display_name = config_data.get('display_name', screener_name)
            description = config_data.get('description', '')

            # Generate schema if not in config
            schema = config_data.get('config_schema', {})

            # Get full config for JSON storage
            full_config = {
                'display_name': display_name,
                'description': description,
                'category': category,
                'parameters': config_data.get('parameters', {}),
                'metadata': config_data.get('metadata', {})
            }
            schema_json = json.dumps(schema)
            config_json = json.dumps(full_config)
            print(f'[DEBUG LOAD] {screener_name}: config_json length = {len(config_json)}')

            # Check if config already exists
            cursor.execute(
                'SELECT id FROM screener_configs WHERE screener_name = ?',
                (screener_name,)
            )
            if cursor.fetchone():
                # Update existing config
                cursor.execute(
                    'UPDATE screener_configs SET display_name = ?, description = ?, '
                    'category = ?, config_json = ?, config_schema = ?, current_version = ? '
                    'WHERE screener_name = ?',
                    (display_name, description, category, config_json, schema_json, 'v1.0', screener_name)
                )
                print(f'[DEBUG] Updated config: {screener_name} (category: {category})')
            else:
                # Insert new config
                cursor.execute(
                    'INSERT INTO screener_configs '
                    '(screener_name, display_name, description, category, config_json, config_schema, current_version) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (screener_name, display_name, description, category, config_json, schema_json, 'v1.0')
                )
                print(f'[DEBUG] Loaded config: {screener_name} (category: {category})')
        except Exception as e:
            print(f'[ERROR] Failed to load config {config_file.name}: {e}')

    conn.commit()
    conn.close()

    loaded_count = len(config_files)
    print(f'[DEBUG] Loaded {loaded_count} screener configurations')

print('[DEBUG] Flask app initialized')



# Monitor API Routes (Mockup - derived from screener results)
@app.route('/api/monitor/screeners')
def get_monitor_screeners():
    """Get list of screeners for monitor view"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT screener_name, display_name, category FROM screener_configs ORDER BY category, screener_name'
    )
    rows = cursor.fetchall()
    conn.close()

    screeners = []
    for row in rows:
        (screener_name, display_name, _category) = row
        screeners.append({
            'name': screener_name,
            'display_name': display_name
        })

    return safe_jsonify({'screeners': screeners})


@app.route('/api/monitor/pipeline')
def get_monitor_pipeline():
    """Get picks for a screener (derived from screener results)"""
    screener_id = request.args.get('screener_id', '')

    if not screener_id:
        return safe_jsonify({'picks': []})

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get latest run date for the screener
    cursor.execute(
        'SELECT MAX(run_date) FROM screener_runs WHERE screener_name = ? AND status = "completed"',
        (screener_id,)
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        conn.close()
        return safe_jsonify({'picks': []})

    latest_date = row[0]

    # Get results for the latest run
    cursor.execute(
        '''SELECT sr.stock_code, sr.stock_name, sr.close_price, sr.turnover, sr.pct_change,
                  sr.extra_data, sre.started_at
           FROM screener_results sr
           JOIN screener_runs sre ON sr.run_id = sre.id
           WHERE sre.screener_name = ? AND sre.run_date = ?
           ORDER BY sr.turnover DESC LIMIT 50''',
        (screener_id, latest_date)
    )
    rows = cursor.fetchall()
    conn.close()

    # Map to Monitor's Pick interface
    picks = []
    for i, row in enumerate(rows):
        (stock_code, stock_name, close_price, _turnover, pct_change, extra_data, started_at) = row

        # Parse extra_data for additional info
        extra = {}
        if extra_data:
            try:
                extra = json.loads(extra_data)
            except:
                pass

        picks.append({
            'id': i + 1,
            'screener_id': screener_id,
            'stock_code': stock_code,
            'stock_name': stock_name or '',
            'entry_date': latest_date,
            'entry_price': close_price or 0,
            'expected_exit_date': '',  # Not applicable
            'status': 'active',  # All latest results are active
            'exit_date': None,
            'exit_reason': None,
            'daily_checks': [{'day': 1, 'close_price': close_price, 'status': 'active'}],
            'created_at': started_at or latest_date,
            'cup_rim_price': extra.get('cup_rim_price'),
            'cup_bottom_price': extra.get('cup_bottom_price'),
            'max_price_seen': extra.get('max_price_seen') or close_price,
            'industry': extra.get('industry'),
            'market_cap': extra.get('market_cap'),
            'pe': extra.get('pe'),
            'pct_change': pct_change
        })

    return safe_jsonify({'picks': picks})


@app.route('/api/monitor/expired', methods=['GET'])
def get_monitor_expired():
    """Get expired picks (placeholder - returns empty for now)"""
    return safe_jsonify({'picks': []})


def _safe_int_arg(name: str, default: int, min_value: int = None, max_value: int = None) -> int:
    """Parse int query arg with bounds"""
    raw = request.args.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default

    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


# Five-Flags API Routes (read-only, safe rollout)
@app.route('/api/five-flags/health', methods=['GET'])
def five_flags_health():
    """Health summary for five-flags data readiness"""
    try:
        conn = get_stock_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool')
        total_pools = cursor.fetchone()['cnt']

        cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool WHERE processed = 0')
        unprocessed_pools = cursor.fetchone()['cnt']

        cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_five_flags')
        total_results = cursor.fetchone()['cnt']

        cursor.execute('SELECT MAX(screen_date) AS latest_date FROM lao_ya_tou_five_flags')
        latest_result_date = cursor.fetchone()['latest_date']

        conn.close()

        status = 'healthy' if total_pools > 0 else 'warning'
        return safe_jsonify({
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'pool_total_count': total_pools,
            'pool_unprocessed_count': unprocessed_pools,
            'result_total_count': total_results,
            'latest_result_date': latest_result_date
        })
    except Exception as e:
        return jsonify({'error': f'five-flags health check failed: {str(e)}'}), 500


@app.route('/api/five-flags/cron-logs', methods=['GET'])
def five_flags_cron_logs():
    """Return tail lines of five-flags cron stdout/stderr logs."""
    try:
        tail = _safe_int_arg('tail', 120, min_value=20, max_value=800)
        logs_dir = DASHBOARD_DIR.parent / 'logs'
        stdout_path = logs_dir / 'five_flags_cron.log'
        stderr_path = logs_dir / 'five_flags_cron_error.log'

        stdout_lines = _read_log_tail(stdout_path, tail)
        stderr_lines = _read_log_tail(stderr_path, tail)

        return safe_jsonify({
            'tail': tail,
            'stdout': {
                'path': str(stdout_path),
                'exists': stdout_path.exists(),
                'updated_at': datetime.fromtimestamp(stdout_path.stat().st_mtime).isoformat() if stdout_path.exists() else None,
                'lines': stdout_lines,
            },
            'stderr': {
                'path': str(stderr_path),
                'exists': stderr_path.exists(),
                'updated_at': datetime.fromtimestamp(stderr_path.stat().st_mtime).isoformat() if stderr_path.exists() else None,
                'lines': stderr_lines,
            }
        })
    except Exception as e:
        return jsonify({'error': f'failed to read five-flags cron logs: {str(e)}'}), 500


@app.route('/api/five-flags/pools', methods=['GET'])
def five_flags_pools():
    """List LaoYaTou pools with filters and pagination"""
    try:
        processed = (request.args.get('processed') or 'all').lower()
        stock_code = request.args.get('stock_code')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        dedupe_stock = _parse_bool_arg('dedupe_stock', False)
        hit_first = _parse_bool_arg('hit_first', False)
        limit = _safe_int_arg('limit', 50, min_value=1, max_value=5000)
        offset = _safe_int_arg('offset', 0, min_value=0)

        where_parts = []
        params = []

        if processed in ('0', '1'):
            where_parts.append('processed = ?')
            params.append(int(processed))
        elif processed != 'all':
            return jsonify({'error': 'Invalid processed value. Use 0, 1, or all.'}), 400

        if stock_code:
            where_parts.append('stock_code = ?')
            params.append(stock_code)

        if start_date:
            where_parts.append('end_date >= ?')
            params.append(start_date)
        if end_date:
            where_parts.append('start_date <= ?')
            params.append(end_date)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

        conn = get_stock_db_connection()
        cursor = conn.cursor()

        if dedupe_stock:
            count_sql = f'SELECT COUNT(DISTINCT stock_code) AS total FROM lao_ya_tou_pool {where_sql}'
            cursor.execute(count_sql, params)
            total = cursor.fetchone()['total']

            order_sql = 'ORDER BY has_hits DESC, stock_code ASC' if hit_first else 'ORDER BY stock_code ASC'
            list_sql = f'''
                SELECT
                    p.stock_code,
                    COALESCE(MAX(NULLIF(p.stock_name, '')), p.stock_code) AS stock_name,
                    COALESCE(
                        MAX(
                            CASE
                                WHEN NULLIF(TRIM(m.sector_lv1), '') IS NOT NULL
                                     AND NULLIF(TRIM(m.sector_lv2), '') IS NOT NULL
                                    THEN NULLIF(TRIM(m.sector_lv1), '') || '/' || NULLIF(TRIM(m.sector_lv2), '')
                                WHEN NULLIF(TRIM(m.sector_lv1), '') IS NOT NULL
                                    THEN NULLIF(TRIM(m.sector_lv1), '')
                                WHEN NULLIF(TRIM(m.sector_lv2), '') IS NOT NULL
                                    THEN NULLIF(TRIM(m.sector_lv2), '')
                                ELSE ''
                            END
                        ),
                        ''
                    ) AS sector_compound,
                    MIN(p.start_date) AS start_date,
                    MAX(p.end_date) AS end_date,
                    SUM(CASE WHEN p.processed = 0 THEN 1 ELSE 0 END) AS unprocessed_count,
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM lao_ya_tou_five_flags f
                            WHERE f.stock_code = p.stock_code
                        ) THEN 1
                        ELSE 0
                    END AS has_hits
                FROM lao_ya_tou_pool p
                LEFT JOIN stock_meta m ON m.code = p.stock_code
                {where_sql}
                GROUP BY p.stock_code
                {order_sql}
                LIMIT ? OFFSET ?
            '''
            cursor.execute(list_sql, [*params, limit, offset])
        else:
            count_sql = f'SELECT COUNT(*) AS total FROM lao_ya_tou_pool {where_sql}'
            cursor.execute(count_sql, params)
            total = cursor.fetchone()['total']

            list_sql = f'''
                SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed
                FROM lao_ya_tou_pool
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            '''
            cursor.execute(list_sql, [*params, limit, offset])
        rows = cursor.fetchall()
        conn.close()

        return safe_jsonify({
            'items': [dict(r) for r in rows],
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'error': f'failed to query five-flags pools: {str(e)}'}), 500


@app.route('/api/five-flags/pools/upload', methods=['POST'])
def five_flags_pool_upload():
    """Upload LaoYaTou pool file and enqueue serial screening job"""
    import os
    import tempfile

    if 'file' not in request.files:
        return jsonify({'error': 'file is required'}), 400

    upload_file = request.files['file']
    if not upload_file or not upload_file.filename:
        return jsonify({'error': 'invalid file'}), 400

    force_overwrite = str(request.form.get('force_overwrite', 'false')).lower() == 'true'
    snapshot_id = request.form.get('snapshot_id')

    temp_dir = tempfile.mkdtemp(prefix='ff_pool_upload_')
    temp_path = os.path.join(temp_dir, upload_file.filename)
    try:
        upload_file.save(temp_path)
        upload_result = handle_lao_ya_tou_pool_upload(
            temp_path,
            force_overwrite=force_overwrite
        )
        if upload_result.get('status') != 'success':
            return jsonify({
                'success': False,
                'error': upload_result.get('message', 'upload failed'),
                'errors': upload_result.get('errors', [])
            }), 400

        queue_job = _enqueue_five_flags_job(
            source='pool_upload',
            pool_ids=[],
            max_workers=None,
            retry_of=None,
            snapshot_id=snapshot_id
        )
        started = _drain_five_flags_queue_once()
        queue_status = 'queued'
        run_id = None
        if started and started.get('job_id') == queue_job.get('job_id'):
            queue_status = 'accepted'
            run_id = started.get('run_id')

        return safe_jsonify({
            'success': True,
            'upload': upload_result,
            'queue': {
                'job_id': queue_job.get('job_id'),
                'status': queue_status,
                'run_id': run_id
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'pool upload failed: {str(e)}'}), 500
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception:
            pass


@app.route('/api/five-flags/unprocessed-summary', methods=['GET'])
def five_flags_unprocessed_summary():
    """Summary view for unprocessed LaoYaTou pools"""
    try:
        conn = get_stock_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool WHERE processed = 0')
        unprocessed_pools = cursor.fetchone()['cnt']

        cursor.execute('''
            SELECT file_name, COUNT(*) AS cnt
            FROM lao_ya_tou_pool
            WHERE processed = 0
            GROUP BY file_name
            ORDER BY cnt DESC, file_name ASC
        ''')
        by_file_name = [dict(r) for r in cursor.fetchall()]

        cursor.execute('''
            SELECT COALESCE(SUM(trading_days), 0) AS estimated_days
            FROM (
                SELECT p.id, COUNT(DISTINCT d.trade_date) AS trading_days
                FROM lao_ya_tou_pool p
                LEFT JOIN daily_prices d
                    ON d.code = p.stock_code
                   AND d.trade_date >= p.start_date
                   AND d.trade_date <= p.end_date
                WHERE p.processed = 0
                GROUP BY p.id
            ) t
        ''')
        unprocessed_dates_estimate = cursor.fetchone()['estimated_days']
        conn.close()

        return safe_jsonify({
            'unprocessed_pools': unprocessed_pools,
            'unprocessed_dates_estimate': unprocessed_dates_estimate,
            'by_file_name': by_file_name
        })
    except Exception as e:
        return jsonify({'error': f'failed to build unprocessed summary: {str(e)}'}), 500


@app.route('/api/five-flags/results', methods=['GET'])
def five_flags_results():
    """Query five-flags result records with filters and pagination"""
    try:
        pool_id = request.args.get('pool_id')
        stock_code = request.args.get('stock_code')
        screener_id = request.args.get('screener_id')
        from_date = request.args.get('from')
        to_date = request.args.get('to')
        sort = (request.args.get('sort') or 'screen_date:desc').lower()
        limit = _safe_int_arg('limit', 50, min_value=1, max_value=500)
        offset = _safe_int_arg('offset', 0, min_value=0)

        order_by = 'screen_date DESC, stock_code ASC'
        if sort == 'screen_date:asc':
            order_by = 'screen_date ASC, stock_code ASC'

        where_parts = []
        params = []

        if pool_id:
            try:
                where_parts.append('pool_id = ?')
                params.append(int(pool_id))
            except ValueError:
                return jsonify({'error': 'pool_id must be integer'}), 400
        if stock_code:
            where_parts.append('stock_code = ?')
            params.append(stock_code)
        if screener_id:
            where_parts.append('screener_id = ?')
            params.append(screener_id)
        if from_date:
            where_parts.append('screen_date >= ?')
            params.append(from_date)
        if to_date:
            where_parts.append('screen_date <= ?')
            params.append(to_date)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

        conn = get_stock_db_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lao_ya_tou_five_flags)")
        table_columns = {row['name'] for row in cursor.fetchall()}
        has_snapshot_id = 'snapshot_id' in table_columns

        count_sql = f'SELECT COUNT(*) AS total FROM lao_ya_tou_five_flags {where_sql}'
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        select_snapshot = ', snapshot_id' if has_snapshot_id else ''

        list_sql = f'''
            SELECT id, pool_id, screener_id, stock_code, stock_name, screen_date,
                   close_price, match_reason, extra_data, created_at{select_snapshot}
            FROM lao_ya_tou_five_flags
            {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        '''
        cursor.execute(list_sql, [*params, limit, offset])
        rows = cursor.fetchall()
        conn.close()

        items = []
        for row in rows:
            record = dict(row)
            if record.get('extra_data'):
                try:
                    record['extra_data'] = json.loads(record['extra_data'])
                except Exception:
                    pass
            if not has_snapshot_id:
                record['snapshot_id'] = 'legacy'
            items.append(record)

        return safe_jsonify({
            'items': items,
            'total': total,
            'limit': limit,
            'offset': offset,
            'dedupe_key': ['stock_code', 'screener_id', 'screen_date', 'snapshot_id']
        })
    except Exception as e:
        return jsonify({'error': f'failed to query five-flags results: {str(e)}'}), 500


@app.route('/api/five-flags/timeline', methods=['GET'])
def five_flags_timeline():
    """Timeline grouped by date for one stock"""
    stock_code = request.args.get('stock_code')
    if not stock_code:
        return jsonify({'error': 'stock_code is required'}), 400

    from_date = request.args.get('from')
    to_date = request.args.get('to')
    include_miss_details = _parse_bool_arg('include_miss_details', False)
    max_diag_cells = 320
    max_diag_raw = request.args.get('max_diag_cells')
    if max_diag_raw:
        try:
            max_diag_cells = max(1, min(5000, int(str(max_diag_raw).strip())))
        except Exception:
            max_diag_cells = 320

    try:
        conn = get_stock_db_connection()
        cursor = conn.cursor()

        where_parts = ['stock_code = ?']
        params = [stock_code]
        if from_date:
            where_parts.append('screen_date >= ?')
            params.append(from_date)
        if to_date:
            where_parts.append('screen_date <= ?')
            params.append(to_date)

        where_sql = ' AND '.join(where_parts)
        cursor.execute(
            f'''
            SELECT screen_date, screener_id, match_reason, close_price, pool_id, created_at, extra_data
            FROM lao_ya_tou_five_flags
            WHERE {where_sql}
            ORDER BY screen_date ASC, screener_id ASC
            ''',
            params
        )
        rows = cursor.fetchall()
        hit_dates = sorted({row['screen_date'] for row in rows})

        selected_dates = []
        if from_date and to_date and from_date <= to_date:
            cursor.execute(
                '''
                SELECT DISTINCT trade_date
                FROM daily_prices
                WHERE code = ? AND trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date ASC
                ''',
                (stock_code, from_date, to_date)
            )
            selected_dates = [r['trade_date'] for r in cursor.fetchall()]
            if not selected_dates:
                selected_dates = list(_iter_dates(from_date, to_date))
        elif hit_dates:
            selected_dates = hit_dates
        else:
            selected_dates = []

        cursor.execute('SELECT name FROM stocks WHERE code = ? LIMIT 1', (stock_code,))
        stock_row = cursor.fetchone()
        stock_name = stock_row['name'] if stock_row and stock_row['name'] else stock_code

        daily_quote_map = {}
        if selected_dates:
            quote_where_parts = ['code = ?']
            quote_params = [stock_code]
            if from_date:
                quote_where_parts.append('trade_date >= ?')
                quote_params.append(from_date)
            if to_date:
                quote_where_parts.append('trade_date <= ?')
                quote_params.append(to_date)
            quote_where_sql = ' AND '.join(quote_where_parts)
            cursor.execute(
                f'''
                SELECT trade_date, open, high, low, close, pct_change, volume, amount, turnover
                FROM daily_prices
                WHERE {quote_where_sql}
                ORDER BY trade_date ASC
                ''',
                quote_params
            )
            for quote in cursor.fetchall():
                daily_quote_map[quote['trade_date']] = {
                    'trade_date': quote['trade_date'],
                    'open': quote['open'],
                    'high': quote['high'],
                    'low': quote['low'],
                    'close': quote['close'],
                    'pct_change': quote['pct_change'],
                    'volume': quote['volume'],
                    'amount': quote['amount'],
                    'turnover': quote['turnover'],
                }
        conn.close()

        def _empty_items():
            return [
                {
                    'screener_id': screener['screener_id'],
                    'label': screener['label'],
                    'hit': False,
                    'reason_hit': '',
                    'reason_miss': f"当日未满足「{screener['label']}」条件。",
                    'failed_checks': [],
                    'first_failed_check': None,
                    'diagnostic_hints': [],
                }
                for screener in FIVE_FLAGS_TIMELINE_SCREENERS
            ]

        timeline_map = {}
        for d in selected_dates:
            timeline_map[d] = {
                'date': d,
                'hits': [],
                'details': [],
                'items': _empty_items(),
            }

        for row in rows:
            d = row['screen_date']
            if d not in timeline_map:
                timeline_map[d] = {
                    'date': d,
                    'hits': [],
                    'details': [],
                    'items': _empty_items(),
                }

            resolved_id = _resolve_five_flags_screener_id(row['screener_id'])
            extra_data = row['extra_data']
            if isinstance(extra_data, str):
                try:
                    extra_data = json.loads(extra_data)
                except Exception:
                    extra_data = {}
            elif not isinstance(extra_data, dict):
                extra_data = {}

            timeline_map[d]['hits'].append(row['screener_id'])
            timeline_map[d]['details'].append({
                'screener_id': row['screener_id'],
                'match_reason': row['match_reason'],
                'reason_hit': row['match_reason'] or '',
                'reason_miss': '',
                'failed_checks': _normalize_failed_checks(extra_data.get('failed_checks')),
                'first_failed_check': _normalize_failed_check(extra_data.get('first_failed_check')),
                'diagnostic_hints': _normalize_text_list(extra_data.get('diagnostic_hints')),
                'close_price': row['close_price'],
                'pool_id': row['pool_id'],
                'created_at': row['created_at']
            })

            if not resolved_id:
                continue
            for item in timeline_map[d]['items']:
                if item['screener_id'] != resolved_id:
                    continue
                item['hit'] = True
                item['reason_hit'] = row['match_reason'] or ''
                item['reason_miss'] = ''
                break

        if include_miss_details and selected_dates:
            total_cells = len(selected_dates) * len(FIVE_FLAGS_TIMELINE_SCREENERS)
            if total_cells <= max_diag_cells:
                from scripts.pool_screener_adapter import ScreenerAdapter

                adapter = ScreenerAdapter(db_path=str(DASHBOARD_DIR.parent / 'data' / 'stock_data.db'))
                for date_str in selected_dates:
                    one_day = timeline_map.get(date_str)
                    if not one_day:
                        continue
                    for item in one_day['items']:
                        if item.get('hit'):
                            continue
                        miss_result = adapter.check_stock(
                            screener_id=item['screener_id'],
                            stock_code=stock_code,
                            stock_name=stock_name,
                            date=date_str,
                            include_miss_details=True
                        )
                        if not isinstance(miss_result, dict):
                            continue
                        if _to_native_bool(miss_result.get('matched')):
                            item['hit'] = True
                            item['reason_hit'] = miss_result.get('reason', '')
                            item['reason_miss'] = ''
                            one_day['hits'].append(item['screener_id'])
                            one_day['details'].append({
                                'screener_id': item['screener_id'],
                                'match_reason': miss_result.get('reason', ''),
                                'reason_hit': miss_result.get('reason', ''),
                                'reason_miss': '',
                                'failed_checks': [],
                                'first_failed_check': None,
                                'diagnostic_hints': [],
                                'close_price': miss_result.get('price'),
                                'pool_id': None,
                                'created_at': None,
                            })
                            continue
                        item['reason_miss'] = miss_result.get('reason_miss') or item['reason_miss']
                        item['failed_checks'] = _normalize_failed_checks(miss_result.get('failed_checks'))
                        item['first_failed_check'] = _normalize_failed_check(miss_result.get('first_failed_check'))
                        item['diagnostic_hints'] = _normalize_text_list(miss_result.get('diagnostic_hints'))

        timeline = [timeline_map[k] for k in sorted(timeline_map.keys())]
        return safe_jsonify({
            'stock_code': stock_code,
            'stock_name': stock_name,
            'diag_meta': {
                'include_miss_details': include_miss_details,
                'max_diag_cells': max_diag_cells,
                'diagnostics_applied': bool(include_miss_details and selected_dates and (len(selected_dates) * len(FIVE_FLAGS_TIMELINE_SCREENERS) <= max_diag_cells))
            },
            'screeners': [
                {'screener_id': item['screener_id'], 'label': item['label']}
                for item in FIVE_FLAGS_TIMELINE_SCREENERS
            ],
            'timeline': timeline,
            'daily_quotes': [daily_quote_map[d] for d in selected_dates if d in daily_quote_map]
        })
    except Exception as e:
        return jsonify({'error': f'failed to query timeline: {str(e)}'}), 500


@app.route('/api/five-flags/diagnose-cell', methods=['GET'])
def five_flags_diagnose_cell():
    """Diagnose one stock-date-screener cell for miss details fallback."""
    stock_code = (request.args.get('stock_code') or '').strip()
    screen_date = (request.args.get('date') or '').strip()
    screener_id = (request.args.get('screener_id') or '').strip()
    stock_name = (request.args.get('stock_name') or '').strip()

    if not stock_code or not screen_date or not screener_id:
        return jsonify({'error': 'stock_code, date, screener_id are required'}), 400

    resolved_id = _resolve_five_flags_screener_id(screener_id)
    if not resolved_id:
        return jsonify({'error': f'invalid screener_id: {screener_id}'}), 400

    try:
        conn = get_stock_db_connection()
        cursor = conn.cursor()

        if not stock_name:
            cursor.execute('SELECT name FROM stocks WHERE code = ? LIMIT 1', (stock_code,))
            row = cursor.fetchone()
            if row and row['name']:
                stock_name = row['name']
            else:
                stock_name = stock_code

        cursor.execute(
            '''
            SELECT trade_date, open, high, low, close, pct_change, volume, amount, turnover
            FROM daily_prices
            WHERE code = ? AND trade_date = ?
            LIMIT 1
            ''',
            (stock_code, screen_date)
        )
        quote_row = cursor.fetchone()
        conn.close()

        daily_quote = dict(quote_row) if quote_row else None

        from scripts.pool_screener_adapter import ScreenerAdapter
        adapter = ScreenerAdapter(db_path=str(DASHBOARD_DIR.parent / 'data' / 'stock_data.db'))
        result = adapter.check_stock(
            screener_id=resolved_id,
            stock_code=stock_code,
            stock_name=stock_name,
            date=screen_date,
            include_miss_details=True
        )

        if not isinstance(result, dict):
            return safe_jsonify({
                'stock_code': stock_code,
                'stock_name': stock_name,
                'date': screen_date,
                'screener_id': resolved_id,
                'matched': False,
                'reason_miss': f"当日未满足「{resolved_id}」条件。",
                'failed_checks': [],
                'first_failed_check': None,
                'diagnostic_hints': [],
                'daily_quote': daily_quote,
            })

        return safe_jsonify({
            'stock_code': stock_code,
            'stock_name': stock_name,
            'date': screen_date,
            'screener_id': resolved_id,
            'matched': _to_native_bool(result.get('matched')),
            'reason_hit': result.get('reason') or '',
            'reason_miss': result.get('reason_miss') or '',
            'failed_checks': _normalize_failed_checks(result.get('failed_checks')),
            'first_failed_check': _normalize_failed_check(result.get('first_failed_check')),
            'diagnostic_hints': _normalize_text_list(result.get('diagnostic_hints')),
            'daily_quote': daily_quote,
            'price': result.get('price'),
        })
    except Exception as e:
        return jsonify({'error': f'failed to diagnose cell: {str(e)}'}), 500


def _load_five_flags_progress():
    """Load five-flags progress file if present"""
    progress_path = DASHBOARD_DIR.parent / 'data' / 'five_flags_screening_progress.json'
    if not progress_path.exists():
        return None
    try:
        with open(progress_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _five_flags_runs_registry_path():
    """Runs registry path for five-flags API"""
    return DASHBOARD_DIR.parent / 'data' / 'five_flags_runs.json'


def _load_five_flags_runs_registry():
    """Load persisted run metadata list"""
    path = _five_flags_runs_registry_path()
    if not path.exists():
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_five_flags_runs_registry(runs):
    """Persist run metadata list"""
    path = _five_flags_runs_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep latest 200 records to bound file size
    runs = sorted(runs, key=lambda r: r.get('requested_at') or '', reverse=True)[:200]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(runs, f, ensure_ascii=False, indent=2)


FIVE_FLAGS_QUEUE_LOCK = threading.Lock()
FIVE_FLAGS_QUEUE_WORKER_STARTED = False
FIVE_FLAGS_DAILY_SCHEDULER_STARTED = False
VALID_MARKET_PHASES = {'WAVE_1', 'WAVE_2', 'WAVE_3', 'WAVE_4', 'WAVE_5', 'WAVE_A', 'WAVE_B', 'WAVE_C'}
VALID_PROFILE_SLOTS = {'active', 'candidate'}
FIVE_FLAGS_DAILY_TRIGGER_HOUR = int(os.environ.get('FIVE_FLAGS_DAILY_TRIGGER_HOUR', '17'))
FIVE_FLAGS_DAILY_TRIGGER_MINUTE = int(os.environ.get('FIVE_FLAGS_DAILY_TRIGGER_MINUTE', '0'))
FIVE_FLAGS_DAILY_ENABLED = os.environ.get('FIVE_FLAGS_DAILY_ENABLED', '1') == '1'
FIVE_FLAGS_EMAIL_TO = os.environ.get('FIVE_FLAGS_EMAIL_TO', '')
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '465'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')


def _five_flags_queue_path():
    """Queue file path for serial five-flags scheduling"""
    return DASHBOARD_DIR.parent / 'data' / 'five_flags_queue.json'


def _read_log_tail(log_path: Path, tail: int = 120) -> list[str]:
    """Read last N lines of a text log file safely."""
    if not log_path.exists() or tail <= 0:
        return []
    with open(log_path, 'r', encoding='utf-8', errors='replace') as fp:
        return list(deque(fp, maxlen=tail))


def _five_flags_daily_scheduler_state_path():
    return DASHBOARD_DIR.parent / 'data' / 'five_flags_daily_scheduler_state.json'


def _five_flags_default_phase_profile_path():
    return DASHBOARD_DIR.parent / 'config' / 'screeners' / 'market_phase_profiles.json'


def _resolve_phase_profile_path(path_str=None):
    if not path_str:
        return _five_flags_default_phase_profile_path()
    candidate = Path(str(path_str))
    if candidate.is_absolute():
        return candidate
    return DASHBOARD_DIR.parent / candidate


def _normalize_market_phase(value):
    if value is None:
        return None
    phase = str(value).strip().upper()
    if not phase:
        return None
    if phase not in VALID_MARKET_PHASES:
        raise ValueError(f'invalid market_phase: {phase}')
    return phase


def _normalize_profile_slot(value, default='active'):
    slot = str(value or default).strip().lower()
    if slot not in VALID_PROFILE_SLOTS:
        raise ValueError(f'invalid profile_slot: {slot}')
    return slot


def _load_phase_profile_doc(path):
    if not path.exists():
        return {'metadata': {}, 'profiles': {'default': {'active': {}, 'candidate': {}}}}
    with open(path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    return _normalize_phase_profile_doc(loaded if isinstance(loaded, dict) else {})


def _normalize_phase_profile_doc(loaded):
    # Backward compatibility with old format: {"default": {...}, "WAVE_1": {...}}
    if 'profiles' in loaded and isinstance(loaded.get('profiles'), dict):
        doc = loaded
    else:
        profiles = {}
        for key, value in loaded.items():
            if not isinstance(value, dict):
                continue
            phase_key = str(key).strip().upper()
            if phase_key == 'DEFAULT':
                phase_key = 'default'
            profiles[phase_key] = {'active': value, 'candidate': {}}
        doc = {'metadata': {}, 'profiles': profiles}

    metadata = doc.get('metadata') if isinstance(doc.get('metadata'), dict) else {}
    profiles = doc.get('profiles') if isinstance(doc.get('profiles'), dict) else {}
    final_profiles = {}
    for key, value in profiles.items():
        phase_key = str(key).strip().upper()
        if phase_key == 'DEFAULT':
            phase_key = 'default'
        if phase_key != 'default' and phase_key not in VALID_MARKET_PHASES:
            continue
        entry = value if isinstance(value, dict) else {}
        active = entry.get('active') if isinstance(entry.get('active'), dict) else {}
        candidate = entry.get('candidate') if isinstance(entry.get('candidate'), dict) else {}
        final_profiles[phase_key] = {'active': active, 'candidate': candidate}
    if 'default' not in final_profiles:
        final_profiles['default'] = {'active': {}, 'candidate': {}}
    return {'metadata': metadata, 'profiles': final_profiles}


def _save_phase_profile_doc(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_phase_profile_doc(doc if isinstance(doc, dict) else {})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def _load_daily_scheduler_state():
    path = _five_flags_daily_scheduler_state_path()
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_daily_scheduler_state(state):
    path = _five_flags_daily_scheduler_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state if isinstance(state, dict) else {}, f, ensure_ascii=False, indent=2)


def _check_five_flags_unprocessed_data_readiness():
    """
    Readiness guard for auto/manual default run.
    Daily catch-up now runs on all pool stocks, so we require:
    1) pool table has records
    2) price table has at least one trade date
    3) at least one pool row needs catch-up to latest_db_trade_date
    """
    conn = get_stock_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool')
        pool_row = cursor.fetchone()
        pool_count = int(pool_row['cnt']) if pool_row and 'cnt' in pool_row.keys() else 0
        if pool_count <= 0:
            return {
                'ready': False,
                'reason': 'no_pools',
                'pool_count': 0,
                'latest_trade_date': None
            }

        cursor.execute('SELECT MAX(trade_date) AS latest_trade_date FROM daily_prices')
        price_row = cursor.fetchone()
        latest_trade_date = (
            str(price_row['latest_trade_date'])
            if price_row and price_row['latest_trade_date']
            else None
        )
        if latest_trade_date is None:
            return {
                'ready': False,
                'reason': 'no_price_data',
                'pool_count': pool_count,
                'latest_trade_date': None
            }

        cursor.execute(
            '''
            SELECT COUNT(*) AS cnt
            FROM lao_ya_tou_pool
            WHERE
                COALESCE(start_date, '9999-12-31') <= ?
                AND (
                    last_screened_date IS NULL
                    OR last_screened_date < ?
                )
            ''',
            (latest_trade_date, latest_trade_date)
        )
        pending_row = cursor.fetchone()
        pending_pool_count = int(pending_row['cnt']) if pending_row and 'cnt' in pending_row.keys() else 0
        if pending_pool_count <= 0:
            return {
                'ready': False,
                'reason': 'up_to_date',
                'pool_count': pool_count,
                'pending_pool_count': 0,
                'latest_trade_date': latest_trade_date
            }

        return {
            'ready': True,
            'reason': 'ready',
            'pool_count': pool_count,
            'pending_pool_count': pending_pool_count,
            'latest_trade_date': latest_trade_date
        }
    finally:
        conn.close()


def _send_email(subject, body):
    if not SMTP_USER or not SMTP_PASSWORD:
        return False, 'smtp credentials not configured'
    if not FIVE_FLAGS_EMAIL_TO:
        return False, 'email recipient not configured'
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
        msg['To'] = FIVE_FLAGS_EMAIL_TO
        msg.set_content(body)
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)


def _notify_daily_run_started(job_id, run_id):
    now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    subject = f'[NeoTrade] Five Flags 日报任务已启动 {now_text}'
    body = (
        'Five Flags 每日任务已启动。\n\n'
        f'- 时间: {now_text}\n'
        f'- job_id: {job_id}\n'
        f'- run_id: {run_id}\n'
        '- 触发方式: daily_auto (17:00)\n'
    )
    return _send_email(subject, body)


def _notify_daily_run_finished(run):
    now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = run.get('status') or 'unknown'
    subject = f'[NeoTrade] Five Flags 日报任务结果 {status.upper()} {now_text}'
    by_screener = run.get('by_screener') or {}
    screener_lines = '\n'.join([f"  - {k}: {v}" for k, v in by_screener.items()]) or '  - 无'
    body = (
        'Five Flags 每日任务简报\n\n'
        f'- 时间: {now_text}\n'
        f"- run_id: {run.get('run_id')}\n"
        f'- 状态: {status}\n'
        f"- 总股票数: {run.get('total_stocks', 0)}\n"
        f"- 已处理: {run.get('processed_stocks', 0)}\n"
        f"- 失败数: {run.get('failed_stocks', 0)}\n"
        f"- 总命中数: {run.get('total_matches', 0)}\n"
        f"- 市场阶段: {run.get('market_phase') or 'default'}\n"
        f"- 参数槽位: {run.get('profile_slot') or 'active'}\n"
        f"- 参数版本: {run.get('profile_version') or 'N/A'}\n\n"
        '按筛选器命中:\n'
        f'{screener_lines}\n'
    )
    return _send_email(subject, body)


def _load_five_flags_queue():
    path = _five_flags_queue_path()
    if not path.exists():
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_five_flags_queue(items):
    path = _five_flags_queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _refresh_five_flags_queue_status(lock_held: bool = False):
    """
    Sync queue item status by associated run status.
    started -> completed/failed when run registry is finalized.
    """
    def _do_refresh():
        queue_items = _load_five_flags_queue()
        if not queue_items:
            return queue_items

        runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
        run_by_id = {r.get('run_id'): r for r in runs}
        changed = False
        now_ts = datetime.now().isoformat()
        pending_finish_notifications = []

        for item in queue_items:
            if item.get('status') != 'started':
                continue
            run_id = item.get('run_id')
            if not run_id:
                continue
            run = run_by_id.get(run_id)
            if not run:
                continue
            run_status = run.get('status')
            # Sync flow runtime fields for better queue observability.
            for key in (
                'flow_id', 'flow_plan_type', 'total_levels', 'current_level',
                'level_duration_ms', 'market_phase', 'phase_param_profile',
                'profile_slot', 'profile_version', 'calibration_note'
            ):
                if key in run and item.get(key) != run.get(key):
                    item[key] = run.get(key)
                    changed = True

            if run_status in ('completed', 'failed'):
                item['status'] = run_status
                item['completed_at'] = run.get('completed_at') or now_ts
                if run_status == 'failed':
                    item['error'] = item.get('error') or 'run failed'
                if item.get('source') == 'daily_auto' and not item.get('finish_email_sent_at'):
                    pending_finish_notifications.append((item, run))
                changed = True

        for item, run in pending_finish_notifications:
            sent_ok, sent_error = _notify_daily_run_finished(run)
            item['finish_email_sent_at'] = datetime.now().isoformat()
            item['finish_email_status'] = 'sent' if sent_ok else 'failed'
            item['finish_email_error'] = sent_error
            changed = True

        if changed:
            _save_five_flags_queue(queue_items)
        return queue_items

    if lock_held:
        return _do_refresh()
    with FIVE_FLAGS_QUEUE_LOCK:
        return _do_refresh()


def _has_active_five_flags_run():
    runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
    active = next((r for r in runs if r.get('status') in ('running', 'accepted')), None)
    if not active:
        return False, None
    if _is_pid_running(active.get('pid')):
        return True, active
    return False, None


def _enqueue_five_flags_job(source: str, pool_ids=None, max_workers=None, retry_of=None,
                            snapshot_id=None, flow_config=None, market_phase=None,
                            phase_profile=None, profile_slot='active', calibration_note=None,
                            as_of_date=None):
    now = datetime.now().isoformat()
    job = {
        'job_id': f'ffq_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:8]}',
        'status': 'queued',
        'source': source,
        'requested_at': now,
        'started_at': None,
        'run_id': None,
        'pool_ids': pool_ids or [],
        'max_workers': max_workers,
        'retry_of': retry_of,
        'snapshot_id': snapshot_id,
        'flow_config': flow_config,
        'market_phase': market_phase,
        'phase_profile': phase_profile,
        'profile_slot': profile_slot,
        'calibration_note': calibration_note,
        'as_of_date': as_of_date,
        'error': None
    }
    with FIVE_FLAGS_QUEUE_LOCK:
        queue_items = _load_five_flags_queue()
        queue_items.append(job)
        _save_five_flags_queue(queue_items)
    return job


def _drain_five_flags_queue_once():
    with FIVE_FLAGS_QUEUE_LOCK:
        queue_items = _refresh_five_flags_queue_status(lock_held=True)
        pending = [x for x in queue_items if x.get('status') == 'queued']
        if not pending:
            return None

        has_active, _ = _has_active_five_flags_run()
        if has_active:
            return None

        target_job = pending[0]
        target_job_id = target_job.get('job_id')

        try:
            start_result = _start_five_flags_run(
                pool_ids=target_job.get('pool_ids') or [],
                max_workers=target_job.get('max_workers'),
                dry_run=False,
                retry_of=target_job.get('retry_of'),
                snapshot_id=target_job.get('snapshot_id'),
                flow_config=target_job.get('flow_config'),
                market_phase=target_job.get('market_phase'),
                phase_profile=target_job.get('phase_profile'),
                profile_slot=target_job.get('profile_slot') or 'active',
                calibration_note=target_job.get('calibration_note'),
                as_of_date=target_job.get('as_of_date')
            )
            for item in queue_items:
                if item.get('job_id') == target_job_id:
                    item['status'] = 'started'
                    item['started_at'] = datetime.now().isoformat()
                    item['run_id'] = start_result.get('run_id')
                    if item.get('source') == 'daily_auto' and not item.get('start_email_sent_at'):
                        sent_ok, sent_error = _notify_daily_run_started(
                            target_job_id,
                            start_result.get('run_id')
                        )
                        item['start_email_sent_at'] = datetime.now().isoformat()
                        item['start_email_status'] = 'sent' if sent_ok else 'failed'
                        item['start_email_error'] = sent_error
            _save_five_flags_queue(queue_items)
            return {'job_id': target_job_id, **start_result}
        except Exception as e:
            for item in queue_items:
                if item.get('job_id') == target_job_id:
                    item['status'] = 'failed'
                    item['error'] = str(e)
            _save_five_flags_queue(queue_items)
            raise


def _start_five_flags_queue_worker():
    global FIVE_FLAGS_QUEUE_WORKER_STARTED
    if FIVE_FLAGS_QUEUE_WORKER_STARTED:
        return

    def _worker_loop():
        while True:
            try:
                _drain_five_flags_queue_once()
            except Exception:
                pass
            time.sleep(5)

    t = threading.Thread(target=_worker_loop, name='five_flags_queue_worker', daemon=True)
    t.start()
    FIVE_FLAGS_QUEUE_WORKER_STARTED = True


def _should_trigger_daily_run(now_dt):
    if not FIVE_FLAGS_DAILY_ENABLED:
        return False
    if now_dt.hour < FIVE_FLAGS_DAILY_TRIGGER_HOUR:
        return False
    if now_dt.hour == FIVE_FLAGS_DAILY_TRIGGER_HOUR and now_dt.minute < FIVE_FLAGS_DAILY_TRIGGER_MINUTE:
        return False
    state = _load_daily_scheduler_state()
    return state.get('last_trigger_date') != now_dt.date().isoformat()


def _start_five_flags_daily_scheduler():
    global FIVE_FLAGS_DAILY_SCHEDULER_STARTED
    if FIVE_FLAGS_DAILY_SCHEDULER_STARTED:
        return

    def _scheduler_loop():
        while True:
            try:
                now_dt = datetime.now()
                if _should_trigger_daily_run(now_dt):
                    with FIVE_FLAGS_QUEUE_LOCK:
                        queue_items = _load_five_flags_queue()
                        has_today_daily = any(
                            (x.get('source') == 'daily_auto') and
                            ((x.get('requested_at') or '')[:10] == now_dt.date().isoformat())
                            for x in queue_items
                        )
                    if not has_today_daily:
                        readiness = _check_five_flags_unprocessed_data_readiness()
                        state = _load_daily_scheduler_state()
                        state['last_checked_at'] = now_dt.isoformat()
                        state['last_guard'] = readiness
                        if readiness.get('ready'):
                            _enqueue_five_flags_job(
                                source='daily_auto',
                                pool_ids=[],
                                max_workers=None,
                                retry_of=None,
                                snapshot_id=None,
                                flow_config=None,
                                market_phase=None,
                                phase_profile=None,
                                profile_slot='active',
                                calibration_note='daily_auto_17:00'
                            )
                            _drain_five_flags_queue_once()
                            state['last_trigger_date'] = now_dt.date().isoformat()
                        elif readiness.get('reason') in ('no_pools', 'up_to_date'):
                            # No pool data or no catch-up needed: mark checked to avoid repeated polling.
                            state['last_trigger_date'] = now_dt.date().isoformat()
                        _save_daily_scheduler_state(state)
            except Exception:
                pass
            time.sleep(30)

    t = threading.Thread(target=_scheduler_loop, name='five_flags_daily_scheduler', daemon=True)
    t.start()
    FIVE_FLAGS_DAILY_SCHEDULER_STARTED = True


def _is_pid_running(pid):
    """Check whether a process id exists"""
    if not pid:
        return False
    try:
        pid_int = int(pid)
        os.kill(pid_int, 0)
        # Treat zombie as not running; avoids stale "running" status forever.
        try:
            import subprocess as _sp
            stat = _sp.check_output(['ps', '-o', 'stat=', '-p', str(pid_int)], text=True).strip()
            if stat.startswith('Z'):
                return False
        except Exception:
            pass
        return True
    except Exception:
        return False


def _refresh_five_flags_run_registry(runs):
    """Refresh status from process existence (read-only check)"""
    changed = False
    now_ts = datetime.now().isoformat()
    progress = _load_five_flags_progress() or {}
    flow_runtime = {
        'flow_id': progress.get('flow_id'),
        'flow_plan_type': progress.get('flow_plan_type'),
        'total_levels': progress.get('total_levels'),
        'current_level': progress.get('current_level'),
        'level_duration_ms': progress.get('level_duration_ms'),
        'market_phase': progress.get('market_phase'),
        'phase_param_profile': progress.get('phase_param_profile'),
        'profile_slot': progress.get('profile_slot'),
        'profile_version': progress.get('profile_version'),
        'calibration_note': progress.get('calibration_note')
    }

    for run in runs:
        status = run.get('status')
        # Only sync runtime flow fields to active runs to avoid rewriting history.
        if flow_runtime.get('flow_id') and status in ('running', 'accepted'):
            for key, value in flow_runtime.items():
                if run.get(key) != value:
                    run[key] = value
                    changed = True

        if status in ('running', 'accepted'):
            pid = run.get('pid')
            if pid and _is_pid_running(pid):
                if status != 'running':
                    run['status'] = 'running'
                    changed = True
            else:
                if status != 'completed' and status != 'failed':
                    # Determine failed/completed from log content when possible.
                    log_file = run.get('log_file')
                    failed = False
                    if log_file:
                        try:
                            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                                content = f.read()
                            failed_markers = ['Traceback (most recent call last):', 'ModuleNotFoundError', 'ERROR']
                            failed = any(m in content for m in failed_markers)
                        except Exception:
                            failed = False
                    run['status'] = 'failed' if failed else 'completed'
                    run['completed_at'] = run.get('completed_at') or now_ts
                    changed = True
    if changed:
        _save_five_flags_runs_registry(runs)
    return runs


def _build_level_timing_summary(runs, limit_runs=20, flow_id=None, spike_threshold=1.8):
    """Aggregate level timing from recent runs for one flow."""
    sorted_runs = sorted(runs, key=lambda r: r.get('requested_at') or '', reverse=True)
    selected_flow_id = flow_id
    selected_plan_type = None
    selected_total_levels = None
    sampled = []

    for run in sorted_runs:
        if run.get('dry_run'):
            continue
        level_map = run.get('level_duration_ms')
        if not isinstance(level_map, dict) or not level_map:
            continue
        run_flow_id = run.get('flow_id')
        if selected_flow_id and run_flow_id != selected_flow_id:
            continue
        if selected_flow_id is None:
            selected_flow_id = run_flow_id
            selected_plan_type = run.get('flow_plan_type')
            selected_total_levels = run.get('total_levels')
        if run.get('flow_plan_type') != selected_plan_type:
            continue
        if run.get('total_levels') != selected_total_levels:
            continue
        sampled.append(run)
        if len(sampled) >= limit_runs:
            break

    if not sampled:
        return {
            'flow_id': selected_flow_id,
            'flow_plan_type': selected_plan_type,
            'total_levels': selected_total_levels,
            'runs_count': 0,
            'spike_threshold': spike_threshold,
            'levels': [],
            'slowest_level': None,
            'spike_alert_levels': [],
            'sampled_run_ids': []
        }

    bucket = {}
    for run in sampled:
        for level_key, value in (run.get('level_duration_ms') or {}).items():
            try:
                level = int(level_key)
                duration_ms = float(value)
            except (TypeError, ValueError):
                continue
            if level not in bucket:
                bucket[level] = []
            bucket[level].append(duration_ms)

    levels = []
    for level in sorted(bucket.keys()):
        values = bucket[level]
        avg_ms = round(sum(values) / len(values), 2)
        min_ms = round(min(values), 2)
        max_ms = round(max(values), 2)
        spike_ratio = round((max_ms / avg_ms), 2) if avg_ms > 0 else 0.0
        levels.append({
            'level': level,
            'avg_ms': avg_ms,
            'min_ms': min_ms,
            'max_ms': max_ms,
            'samples': len(values),
            'spike_ratio': spike_ratio,
            'spike_alert': spike_ratio >= spike_threshold and len(values) >= 3
        })

    slowest_level = None
    if levels:
        slowest = max(levels, key=lambda x: x.get('avg_ms', 0))
        slowest_level = {
            'level': slowest['level'],
            'avg_ms': slowest['avg_ms'],
            'percent_of_total_avg': round(
                (slowest['avg_ms'] / sum(x.get('avg_ms', 0) for x in levels)) * 100, 2
            ) if sum(x.get('avg_ms', 0) for x in levels) > 0 else 0.0
        }

    return {
        'flow_id': selected_flow_id,
        'flow_plan_type': selected_plan_type,
        'total_levels': selected_total_levels,
        'runs_count': len(sampled),
        'spike_threshold': spike_threshold,
        'levels': levels,
        'slowest_level': slowest_level,
        'spike_alert_levels': [x['level'] for x in levels if x.get('spike_alert')],
        'sampled_run_ids': [r.get('run_id') for r in sampled]
    }


def _start_five_flags_run(pool_ids=None, max_workers=None, dry_run=False,
                          retry_of=None, snapshot_id=None, flow_config=None,
                          market_phase=None, phase_profile=None, profile_slot='active',
                          calibration_note=None, as_of_date=None):
    """
    Start five-flags screening subprocess in controlled async mode.
    Returns dict payload for API response.
    """
    project_root = DASHBOARD_DIR.parent
    script_path = project_root / 'scripts' / 'run_five_flags_pool_screening.py'
    if not script_path.exists():
        raise FileNotFoundError(f'five-flags script not found: {script_path}')

    run_id = f'ffrun_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid.uuid4().hex[:8]}'

    # dry_run only validates input and returns accepted preview; no process started
    if dry_run:
        return {
            'run_id': run_id,
            'status': 'dry_run',
            'queued_pools': len(pool_ids or []),
            'snapshot_id': snapshot_id,
            'flow_config': flow_config,
            'market_phase': market_phase,
            'phase_profile': phase_profile,
            'profile_slot': profile_slot,
            'calibration_note': calibration_note,
            'as_of_date': as_of_date,
            'dry_run': True
        }

    cmd = [sys.executable, str(script_path)]
    if max_workers is not None:
        cmd.extend(['--max-workers', str(max_workers)])
    if pool_ids:
        cmd.extend(['--pool-ids', ','.join(str(x) for x in pool_ids)])
    if flow_config:
        cmd.extend(['--flow-config', str(flow_config)])
    if market_phase:
        cmd.extend(['--market-phase', str(market_phase)])
    if phase_profile:
        cmd.extend(['--phase-profile', str(phase_profile)])
    if profile_slot:
        cmd.extend(['--profile-slot', str(profile_slot)])
    if calibration_note:
        cmd.extend(['--calibration-note', str(calibration_note)])
    if as_of_date:
        cmd.extend(['--as-of-date', str(as_of_date)])

    logs_dir = project_root / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f'five_flags_run_{run_id}.log'

    # Launch detached-ish subprocess and redirect output to file
    log_fp = open(log_file, 'a', encoding='utf-8')
    proc = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=log_fp,
        stderr=log_fp
    )
    log_fp.close()

    runs = _load_five_flags_runs_registry()
    record = {
        'run_id': run_id,
        'status': 'running',
        'requested_at': datetime.now().isoformat(),
        'started_at': datetime.now().isoformat(),
        'completed_at': None,
        'pid': proc.pid,
        'pool_ids': pool_ids or [],
        'max_workers': max_workers,
        'retry_of': retry_of,
        'flow_config': flow_config,
        'market_phase': market_phase,
        'phase_profile': phase_profile,
        'profile_slot': profile_slot,
        'calibration_note': calibration_note,
        'as_of_date': as_of_date,
        'dry_run': False,
        'log_file': str(log_file),
        'command': cmd
    }
    runs.append(record)
    _save_five_flags_runs_registry(runs)

    return {
        'run_id': run_id,
        'status': 'accepted',
        'queued_pools': len(pool_ids or []),
        'pid': proc.pid,
        'flow_config': flow_config,
        'market_phase': market_phase,
        'phase_profile': phase_profile,
        'profile_slot': profile_slot,
        'calibration_note': calibration_note,
        'as_of_date': as_of_date,
        'dry_run': False
    }


def _build_five_flags_run_view(run_id: str = 'latest'):
    """Build run metadata from progress file + DB summary (read-only compatibility mode)"""
    progress = _load_five_flags_progress() or {}

    start_time = progress.get('start_time')
    last_update = progress.get('last_update')
    total_stocks = int(progress.get('total_stocks') or 0)
    processed_stocks = int(progress.get('processed_stocks') or 0)
    failed_stocks = int(progress.get('failed_stocks') or 0)
    statistics = progress.get('statistics') or {}
    total_matches = int(statistics.get('total_matches') or 0)
    by_screener = statistics.get('by_screener') or {}
    flow_id = progress.get('flow_id')
    flow_plan_type = progress.get('flow_plan_type')
    total_levels = progress.get('total_levels')
    current_level = progress.get('current_level')
    level_duration_ms = progress.get('level_duration_ms') or {}
    market_phase = progress.get('market_phase')
    phase_param_profile = progress.get('phase_param_profile') or {}
    profile_slot = progress.get('profile_slot')
    profile_version = progress.get('profile_version')
    calibration_note = progress.get('calibration_note')

    # Fallback to database if progress file is missing or empty
    conn = get_stock_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool')
    db_total_pools = cursor.fetchone()['cnt']
    cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool WHERE processed = 1')
    db_processed_pools = cursor.fetchone()['cnt']
    cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool WHERE processed = 0')
    db_unprocessed_pools = cursor.fetchone()['cnt']
    cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_five_flags')
    db_total_matches = cursor.fetchone()['cnt']
    cursor.execute('SELECT MAX(created_at) AS latest_created_at FROM lao_ya_tou_five_flags')
    latest_created_at = cursor.fetchone()['latest_created_at']
    conn.close()

    if total_stocks <= 0:
        total_stocks = db_total_pools
    if processed_stocks <= 0 and db_processed_pools > 0:
        processed_stocks = db_processed_pools
    if total_matches <= 0:
        total_matches = db_total_matches

    if failed_stocks < 0:
        failed_stocks = 0

    if total_stocks > 0:
        percent = round((processed_stocks / total_stocks) * 100, 2)
    else:
        percent = 0.0

    status = 'completed'
    if total_stocks == 0 and db_unprocessed_pools > 0:
        status = 'pending'
    elif start_time and (not last_update or db_unprocessed_pools > 0):
        status = 'running' if processed_stocks < total_stocks else 'completed'
    elif db_unprocessed_pools > 0 and processed_stocks < total_stocks:
        status = 'partial'

    run = {
        'run_id': run_id,
        'status': status,
        'started_at': start_time,
        'last_update': last_update or latest_created_at,
        'completed_at': latest_created_at if status == 'completed' else None,
        'total_stocks': total_stocks,
        'processed_stocks': processed_stocks,
        'failed_stocks': failed_stocks,
        'total_matches': total_matches,
        'by_screener': by_screener,
        'flow_id': flow_id,
        'flow_plan_type': flow_plan_type,
        'total_levels': total_levels,
        'current_level': current_level,
        'level_duration_ms': level_duration_ms,
        'market_phase': market_phase,
        'phase_param_profile': phase_param_profile,
        'profile_slot': profile_slot,
        'profile_version': profile_version,
        'calibration_note': calibration_note,
        'source': 'progress_file+db_aggregate'
    }
    run['progress'] = {
        'percent': percent,
        'processed_stocks': processed_stocks,
        'total_stocks': total_stocks
    }
    return run


@app.route('/api/five-flags/runs', methods=['GET'])
def five_flags_runs():
    """List five-flags runs"""
    try:
        _drain_five_flags_queue_once()
        limit = _safe_int_arg('limit', 20, min_value=1, max_value=100)
        offset = _safe_int_arg('offset', 0, min_value=0)
        status_filter = (request.args.get('status') or '').strip().lower()

        runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
        items = sorted(runs, key=lambda r: r.get('requested_at') or '', reverse=True)
        if not items:
            # Backward-compatible fallback when registry does not exist yet
            items = [_build_five_flags_run_view('latest')]
        if status_filter:
            items = [r for r in items if r.get('status') == status_filter]

        total = len(items)
        paged = items[offset:offset + limit]
        return safe_jsonify({
            'items': paged,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'error': f'failed to query five-flags runs: {str(e)}'}), 500


@app.route('/api/five-flags/runs/<run_id>', methods=['GET'])
def five_flags_run_detail(run_id):
    """Get five-flags run detail"""
    try:
        _drain_five_flags_queue_once()
        runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
        run = next((r for r in runs if r.get('run_id') == run_id), None)
        if run is None:
            if run_id == 'latest':
                run = _build_five_flags_run_view('latest')
            else:
                return jsonify({'error': f'run_id not found: {run_id}'}), 404

        if 'progress' not in run:
            total = int(run.get('total_stocks') or 0)
            done = int(run.get('processed_stocks') or 0)
            run['progress'] = {
                'percent': round((done / total) * 100, 2) if total > 0 else 0.0,
                'processed_stocks': done,
                'total_stocks': total
            }
        return safe_jsonify({
            'run': run,
            'progress': run.get('progress', {}),
            'stats': {
                'total_matches': run.get('total_matches', 0),
                'by_screener': run.get('by_screener', {})
            },
            'errors': []
        })
    except Exception as e:
        return jsonify({'error': f'failed to query run detail: {str(e)}'}), 500


@app.route('/api/five-flags/flow/level-timing', methods=['GET'])
def five_flags_flow_level_timing():
    """Aggregate level timing summary from recent runs."""
    try:
        _drain_five_flags_queue_once()
        limit_runs = _safe_int_arg('limit_runs', 20, min_value=1, max_value=100)
        flow_id = (request.args.get('flow_id') or '').strip() or None
        spike_threshold = request.args.get('spike_threshold', default=1.8, type=float)
        if spike_threshold is None:
            return jsonify({'error': 'spike_threshold must be float'}), 400
        if spike_threshold < 1.0 or spike_threshold > 10.0:
            return jsonify({'error': 'spike_threshold must be between 1.0 and 10.0'}), 400

        runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
        summary = _build_level_timing_summary(
            runs,
            limit_runs=limit_runs,
            flow_id=flow_id,
            spike_threshold=spike_threshold
        )

        return safe_jsonify({
            'summary': summary,
            'limit_runs': limit_runs,
            'spike_threshold': spike_threshold
        })
    except Exception as e:
        return jsonify({'error': f'failed to query level timing summary: {str(e)}'}), 500


@app.route('/api/five-flags/phase-profile/publish', methods=['POST'])
def five_flags_phase_profile_publish():
    """Publish one phase profile slot to another slot, e.g. candidate -> active."""
    try:
        payload = request.get_json(silent=True) or {}
        raw_phase = payload.get('market_phase')
        if raw_phase is None or str(raw_phase).strip().lower() == 'default':
            market_phase = 'default'
        else:
            market_phase = _normalize_market_phase(raw_phase)

        from_slot = _normalize_profile_slot(payload.get('from_slot'), default='candidate')
        to_slot = _normalize_profile_slot(payload.get('to_slot'), default='active')
        if from_slot == to_slot:
            return jsonify({'error': 'from_slot and to_slot must be different'}), 400

        profile_path = _resolve_phase_profile_path(payload.get('phase_profile'))
        doc = _load_phase_profile_doc(profile_path)
        profiles = doc.setdefault('profiles', {})
        phase_entry = profiles.setdefault(market_phase, {'active': {}, 'candidate': {}})
        source_profile = phase_entry.get(from_slot) if isinstance(phase_entry.get(from_slot), dict) else {}
        if not source_profile:
            return jsonify({
                'error': f'cannot publish empty profile: phase={market_phase}, slot={from_slot}'
            }), 400

        phase_entry[to_slot] = json.loads(json.dumps(source_profile, ensure_ascii=False))
        metadata = doc.setdefault('metadata', {})
        metadata['version'] = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
        metadata['updated_at'] = datetime.now().isoformat()
        metadata['last_publish'] = {
            'market_phase': market_phase,
            'from_slot': from_slot,
            'to_slot': to_slot,
            'published_by': (payload.get('published_by') or 'api').strip() or 'api',
            'calibration_note': (payload.get('calibration_note') or '').strip() or None,
            'published_at': datetime.now().isoformat()
        }
        _save_phase_profile_doc(profile_path, doc)

        return safe_jsonify({
            'status': 'published',
            'phase_profile': str(profile_path),
            'market_phase': market_phase,
            'from_slot': from_slot,
            'to_slot': to_slot,
            'profile_version': metadata.get('version'),
            'override_screeners': sorted(list(source_profile.keys()))
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'failed to publish phase profile: {str(e)}'}), 500


@app.route('/api/five-flags/run', methods=['POST'])
def five_flags_run():
    """Enqueue five-flags screening task (serial scheduler)"""
    try:
        payload = request.get_json(silent=True) or {}
        pool_ids = payload.get('pool_ids') or []
        flow_config = payload.get('flow_config')
        market_phase = _normalize_market_phase(payload.get('market_phase'))
        phase_profile = payload.get('phase_profile')
        profile_slot = _normalize_profile_slot(payload.get('profile_slot'), default='active')
        calibration_note = (payload.get('calibration_note') or '').strip() or None
        as_of_date = (payload.get('as_of_date') or '').strip() or None
        dry_run = bool(payload.get('dry_run', False))
        max_workers = payload.get('max_workers')

        if pool_ids and not isinstance(pool_ids, list):
            return jsonify({'error': 'pool_ids must be an array of integers'}), 400
        normalized_pool_ids = []
        for pid in pool_ids:
            try:
                v = int(pid)
            except (TypeError, ValueError):
                return jsonify({'error': f'invalid pool_id: {pid}'}), 400
            if v <= 0:
                return jsonify({'error': f'invalid pool_id: {pid}'}), 400
            normalized_pool_ids.append(v)

        if max_workers is not None:
            try:
                max_workers = int(max_workers)
            except (TypeError, ValueError):
                return jsonify({'error': 'max_workers must be integer'}), 400
            max_workers = max(1, min(8, max_workers))

        # For default manual run (no explicit pool_ids), apply same readiness guard as daily_auto.
        if not normalized_pool_ids and not dry_run:
            readiness = _check_five_flags_unprocessed_data_readiness()
            if not readiness.get('ready'):
                return safe_jsonify({
                    'status': 'skipped',
                    'accepted': False,
                    'reason': readiness.get('reason'),
                    'guard': readiness
                }), 200

        if dry_run:
            result = _start_five_flags_run(
                pool_ids=normalized_pool_ids,
                max_workers=max_workers,
                dry_run=True,
                snapshot_id=payload.get('snapshot_id'),
                flow_config=flow_config,
                market_phase=market_phase,
                phase_profile=phase_profile,
                profile_slot=profile_slot,
                calibration_note=calibration_note,
                as_of_date=as_of_date
            )
            return safe_jsonify(result), 202

        queue_job = _enqueue_five_flags_job(
            source='manual_run',
            pool_ids=normalized_pool_ids,
            max_workers=max_workers,
            retry_of=None,
            snapshot_id=payload.get('snapshot_id'),
            flow_config=flow_config,
            market_phase=market_phase,
            phase_profile=phase_profile,
            profile_slot=profile_slot,
            calibration_note=calibration_note,
            as_of_date=as_of_date
        )
        started = _drain_five_flags_queue_once()
        queued_status = 'queued'
        run_id = None
        if started and started.get('job_id') == queue_job.get('job_id'):
            queued_status = 'accepted'
            run_id = started.get('run_id')

        return safe_jsonify({
            'job_id': queue_job.get('job_id'),
            'status': queued_status,
            'queue_status': queued_status,
            'run_id': run_id,
            'accepted': queued_status == 'accepted',
            'queued_pools': len(normalized_pool_ids),
            'market_phase': market_phase,
            'phase_profile': phase_profile,
            'profile_slot': profile_slot,
            'calibration_note': calibration_note,
            'as_of_date': as_of_date
        }), 202
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'failed to start five-flags run: {str(e)}'}), 500


@app.route('/api/five-flags/retry-failed', methods=['POST'])
def five_flags_retry_failed():
    """Retry failed pool items by explicit pool_ids (serial queued)"""
    try:
        payload = request.get_json(silent=True) or {}
        pool_ids = payload.get('pool_ids') or []
        flow_config = payload.get('flow_config')
        market_phase = _normalize_market_phase(payload.get('market_phase'))
        phase_profile = payload.get('phase_profile')
        profile_slot = _normalize_profile_slot(payload.get('profile_slot'), default='active')
        calibration_note = (payload.get('calibration_note') or '').strip() or None
        if not pool_ids:
            return jsonify({'error': 'pool_ids is required for retry'}), 400
        if not isinstance(pool_ids, list):
            return jsonify({'error': 'pool_ids must be an array of integers'}), 400

        normalized_pool_ids = []
        for pid in pool_ids:
            try:
                v = int(pid)
            except (TypeError, ValueError):
                return jsonify({'error': f'invalid pool_id: {pid}'}), 400
            if v <= 0:
                return jsonify({'error': f'invalid pool_id: {pid}'}), 400
            normalized_pool_ids.append(v)

        max_workers = payload.get('max_workers')
        if max_workers is not None:
            try:
                max_workers = int(max_workers)
            except (TypeError, ValueError):
                return jsonify({'error': 'max_workers must be integer'}), 400
            max_workers = max(1, min(8, max_workers))

        queue_job = _enqueue_five_flags_job(
            source='retry_failed',
            pool_ids=normalized_pool_ids,
            max_workers=max_workers,
            retry_of=payload.get('run_id'),
            flow_config=flow_config,
            market_phase=market_phase,
            phase_profile=phase_profile,
            profile_slot=profile_slot,
            calibration_note=calibration_note
        )
        started = _drain_five_flags_queue_once()
        queued_status = 'queued'
        run_id = None
        if started and started.get('job_id') == queue_job.get('job_id'):
            queued_status = 'accepted'
            run_id = started.get('run_id')

        return safe_jsonify({
            'job_id': queue_job.get('job_id'),
            'retry_run_id': run_id,
            'status': queued_status,
            'queue_status': queued_status,
            'accepted': queued_status == 'accepted',
            'retry_count': len(normalized_pool_ids),
            'market_phase': market_phase,
            'phase_profile': phase_profile,
            'profile_slot': profile_slot,
            'calibration_note': calibration_note
        }), 202
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'failed to retry failed pools: {str(e)}'}), 500


@app.route('/api/five-flags/queue', methods=['GET'])
def five_flags_queue():
    """Query five-flags serial queue status"""
    try:
        _drain_five_flags_queue_once()
        limit = _safe_int_arg('limit', 50, min_value=1, max_value=500)
        items = sorted(_refresh_five_flags_queue_status(), key=lambda x: x.get('requested_at') or '', reverse=True)
        queue_items = items[:limit]
        stats = {
            'queued': len([x for x in items if x.get('status') == 'queued']),
            'started': len([x for x in items if x.get('status') == 'started']),
            'completed': len([x for x in items if x.get('status') == 'completed']),
            'failed': len([x for x in items if x.get('status') == 'failed'])
        }
        return safe_jsonify({
            'items': queue_items,
            'stats': stats,
            'limit': limit
        })
    except Exception as e:
        return jsonify({'error': f'failed to query queue: {str(e)}'}), 500


@app.route('/api/five-flags/queue/<job_id>', methods=['GET'])
def five_flags_queue_detail(job_id):
    """Query one queue job by job_id"""
    try:
        _drain_five_flags_queue_once()
        items = _refresh_five_flags_queue_status()
        job = next((x for x in items if x.get('job_id') == job_id), None)
        if not job:
            return jsonify({'error': f'job_id not found: {job_id}'}), 404
        return safe_jsonify({'job': job})
    except Exception as e:
        return jsonify({'error': f'failed to query queue detail: {str(e)}'}), 500


@app.route('/api/five-flags/pools/upload-status/<job_id>', methods=['GET'])
def five_flags_pool_upload_status(job_id):
    """Query upload-triggered queue status by job_id"""
    try:
        _drain_five_flags_queue_once()
        items = _refresh_five_flags_queue_status()
        job = next((x for x in items if x.get('job_id') == job_id), None)
        if not job:
            return jsonify({'error': f'job_id not found: {job_id}'}), 404
        if job.get('source') != 'pool_upload':
            return jsonify({'error': f'job_id is not a pool_upload job: {job_id}'}), 400
        return safe_jsonify({'job': job})
    except Exception as e:
        return jsonify({'error': f'failed to query upload status: {str(e)}'}), 500


_start_five_flags_queue_worker()
_start_five_flags_daily_scheduler()


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 8765))
    print(f'[DEBUG] Starting Flask server on port {port}...')
    app.run(host='0.0.0.0', port=port, debug=False)
