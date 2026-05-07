#!/usr/bin/env python3
"""
Flask Backend API for Trading Screener Dashboard
"""
import os
import sys
import json
import math
import re
import uuid
import csv
import sqlite3
import gzip
import mimetypes
import subprocess
import threading
import time
import smtplib
import ssl
import logging
from collections import deque
from pathlib import Path
from datetime import datetime, date, timedelta
from functools import wraps
from email.message import EmailMessage

from flask import Flask, jsonify, request, send_from_directory, send_file, Response
from flask_compress import Compress
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
    init_db, get_db_connection, get_stock_db_connection, get_results_by_date, get_run,
    log_access, save_screener_config, compute_five_flags_unprocessed_data_readiness
)
from validators import validate_screener_config, validate_screener_config_update

# Import excel upload handler
from excel_upload import handle_excel_upload, handle_lao_ya_tou_pool_upload

from assistant_learning import assistant_learning_bp, save_rule_run

# Import screeners module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "screeners_module", DASHBOARD_DIR / "screeners.py"
)
screeners_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screeners_module)
register_discovered_screeners = screeners_module.register_discovered_screeners
run_screener_subprocess = screeners_module.run_screener_subprocess

logger = logging.getLogger(__name__)


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
        mimetype='application/json',
        headers={
            'Cache-Control': 'no-store',
            'Pragma': 'no-cache',
        }
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
        from config_loader import ConfigLoader
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

app.config['COMPRESS_MIMETYPES'] = [
    'text/html',
    'text/css',
    'application/javascript',
    'text/javascript',
    'application/json',
    'image/svg+xml',
]
app.config['COMPRESS_LEVEL'] = 6
app.config['COMPRESS_MIN_SIZE'] = 512

Compress(app)

ASSET_GZIP_CACHE = {}
ASSET_GZIP_CACHE_LOCK = threading.Lock()


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

app.register_blueprint(assistant_learning_bp)


# Before request handler
@app.before_request
def before_request():
    # Health check不需要认证
    if request.path == '/api/health':
        return None

    forwarded_for = request.headers.get('X-Forwarded-For')
    remote_ip = request.remote_addr or ''
    is_direct_loopback = remote_ip in ('127.0.0.1', '::1') and not forwarded_for
    log_ip = remote_ip
    if remote_ip in ('127.0.0.1', '::1') and forwarded_for:
        log_ip = (forwarded_for.split(',', 1)[0] or '').strip() or remote_ip

    # Log access for main pages
    if request.path == '/' or (not request.path.startswith('/api/') and
                               not request.path.startswith('/assets/')):
        try:
            log_access(log_ip, request.user_agent.string, request.path)
        except:
            pass

    # Non-local requests need auth
    if not is_direct_loopback:
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
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    assets_dir = (DASHBOARD_DIR.parent / 'frontend/dist/assets').resolve()
    file_path = (assets_dir / filename).resolve()
    if assets_dir not in file_path.parents and file_path != assets_dir:
        return jsonify({'error': 'invalid asset path'}), 400
    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'asset not found'}), 404

    accept_encoding = (request.headers.get('Accept-Encoding') or '').lower()
    ext = file_path.suffix.lower()
    compressible = ext in ('.js', '.css', '.svg', '.json', '.map', '.txt')
    if compressible and 'gzip' in accept_encoding:
        try:
            mtime = file_path.stat().st_mtime
        except Exception:
            mtime = None
        cache_key = (str(file_path), mtime)
        with ASSET_GZIP_CACHE_LOCK:
            cached = ASSET_GZIP_CACHE.get(cache_key)
        if cached is None:
            raw = file_path.read_bytes()
            gz = gzip.compress(raw, compresslevel=6)
            with ASSET_GZIP_CACHE_LOCK:
                ASSET_GZIP_CACHE[cache_key] = gz
        else:
            gz = cached
        content_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
        resp = Response(gz, mimetype=content_type)
        resp.headers['Content-Encoding'] = 'gzip'
        resp.headers['Vary'] = 'Accept-Encoding'
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return resp

    response = send_from_directory(assets_dir, filename)
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
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# API Routes
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


def _get_frontend_build_fingerprint() -> dict:
    dist_dir = DASHBOARD_DIR.parent / 'frontend' / 'dist'
    index_path = dist_dir / 'index.html'
    if not index_path.exists():
        return {'available': False, 'reason': 'dist_index_missing'}

    try:
        html = index_path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return {'available': False, 'reason': 'dist_index_unreadable'}

    marker = 'src="/assets/'
    start = html.find(marker)
    if start < 0:
        return {'available': False, 'reason': 'entry_script_not_found'}
    start += len('src="')
    end = html.find('"', start)
    if end < 0:
        return {'available': False, 'reason': 'entry_script_parse_failed'}

    entry_src = html[start:end]
    entry_js_path = dist_dir / entry_src.lstrip('/')
    entry_mtime = None
    if entry_js_path.exists():
        try:
            entry_mtime = datetime.fromtimestamp(entry_js_path.stat().st_mtime).isoformat()
        except Exception:
            entry_mtime = None

    entry_hash = None
    entry_name = Path(entry_src).name
    if entry_name.startswith('index-') and entry_name.endswith('.js'):
        entry_hash = entry_name[len('index-'):-len('.js')] or None

    return {
        'available': True,
        'index_path': str(index_path),
        'entry_src': entry_src,
        'entry_hash': entry_hash,
        'entry_mtime': entry_mtime
    }


@app.route('/api/version', methods=['GET'])
def api_version():
    fingerprint = _get_frontend_build_fingerprint()
    payload = {
        'server_time': datetime.now().isoformat(),
        'frontend': fingerprint
    }
    resp = safe_jsonify(payload)
    resp.headers['Cache-Control'] = 'no-store, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


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
        run_result = run_screener_subprocess(screener_name, run_date)
        if isinstance(run_result, dict) and not bool(run_result.get('success')):
            return safe_jsonify({
                'status': 'failed',
                'screener': screener_name,
                'error': run_result.get('error') or 'run failed',
                'run_result': run_result,
                'requested_date': run_date,
                'effective_trade_date': run_date,
            }), 500

        return safe_jsonify({
            'status': 'success',
            'screener': screener_name,
            'run_id': run_result,
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
    from pathlib import Path as _Path
    from werkzeug.utils import secure_filename as _secure_filename
    original_name = _Path(str(file.filename)).name
    safe_name = _secure_filename(original_name) or f"upload_{uuid.uuid4().hex}"
    temp_path = os.path.join(temp_dir, safe_name)

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
        result = handle_excel_upload(temp_path, force_update=force_update, original_filename=original_name)
        logger.info(f"Upload result: {result['status']}, message={result.get('message', '')}")

        # Clean up temp file
        os.remove(temp_path)
        os.rmdir(temp_dir)

        if result['status'] in ['success', 'warning']:
            return safe_jsonify({
                'success': True,
                'status': result['status'],
                'message': result['message'],
                'file_name': original_name,
                'trade_date': result['trade_date'],
                'daily_prices': result['daily_prices'],
                'stock_metadata': result['stock_metadata'],
                'warnings': result.get('warnings', []),
                'errors': result.get('errors', [])
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

            cursor.execute(
                'SELECT config_json, current_version FROM screener_configs WHERE screener_name = ?',
                (screener_name,)
            )
            existing_row = cursor.fetchone()

            if existing_row:
                existing_config_json = existing_row['config_json'] if isinstance(existing_row, dict) else existing_row[0]
                try:
                    existing_cfg = json.loads(existing_config_json) if existing_config_json else {}
                except Exception:
                    existing_cfg = {}

                has_parameters = isinstance(existing_cfg, dict) and isinstance(existing_cfg.get('parameters'), dict) and len(existing_cfg.get('parameters') or {}) > 0
                if not has_parameters:
                    existing_version = existing_row['current_version'] if isinstance(existing_row, dict) else existing_row[1]
                    cursor.execute(
                        'UPDATE screener_configs SET display_name = ?, description = ?, '
                        'category = ?, config_json = ?, config_schema = ?, current_version = ? '
                        'WHERE screener_name = ?',
                        (
                            display_name,
                            description,
                            category,
                            config_json,
                            schema_json,
                            existing_version or 'v1.0',
                            screener_name,
                        )
                    )
                    print(f'[DEBUG] Initialized missing config: {screener_name} (category: {category})')
                else:
                    print(f'[DEBUG] Kept existing config: {screener_name} (category: {category})')
            else:
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


STRATEGY_RUNS_LOCK = threading.Lock()
ALLOWED_STRATEGY_IDS = {'neil_turtle_short', 'triple_screen'}
ALLOWED_TASK_TYPES = {'backfill', 'daily'}
ALLOWED_EXECUTE_MODES = {'dry_run', 'execute'}


def _strategy_runs_registry_path():
    """Registry path for generic strategy run metadata."""
    return DASHBOARD_DIR.parent / 'data' / 'strategy_runs.json'


def _load_strategy_runs_registry():
    """Load persisted strategy run list."""
    path = _strategy_runs_registry_path()
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


def _save_strategy_runs_registry(runs):
    """Persist strategy run list."""
    path = _strategy_runs_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    runs = [r for r in (runs or []) if isinstance(r, dict)]
    runs = sorted(runs, key=lambda r: r.get('requested_at') or '', reverse=True)[:300]

    tmp_path = path.with_suffix(path.suffix + '.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(runs, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def _normalize_strategy_run_input(payload):
    """Validate and normalize strategy run request payload."""
    body = payload if isinstance(payload, dict) else {}
    strategy_id = str(body.get('strategy_id') or '').strip().lower()
    task_type = str(body.get('task_type') or '').strip().lower()
    execute_mode = str(body.get('execute_mode') or 'dry_run').strip().lower()
    as_of_date = str(body.get('as_of_date') or '').strip()
    stock_codes = str(body.get('stock_codes') or '').strip()
    params = body.get('params')
    export_pdf = bool(body.get('export_pdf', True))

    if strategy_id not in ALLOWED_STRATEGY_IDS:
        raise ValueError(f'invalid strategy_id: {strategy_id}')
    if task_type not in ALLOWED_TASK_TYPES:
        raise ValueError(f'invalid task_type: {task_type}')
    if execute_mode not in ALLOWED_EXECUTE_MODES:
        raise ValueError(f'invalid execute_mode: {execute_mode}')
    if params not in (None, {}):
        raise ValueError('v1 does not support runtime params override; update strategy config first')

    return {
        'strategy_id': strategy_id,
        'task_type': task_type,
        'execute_mode': execute_mode,
        'as_of_date': as_of_date or None,
        'stock_codes': stock_codes or None,
        'params': params or {},
        'export_pdf': export_pdf,
    }


def _strategy_run_log_dir():
    path = DASHBOARD_DIR.parent / 'logs' / 'strategy_runs'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_strategy_script_command(run_id: str, payload: dict):
    """Build script command for strategy task execution."""
    workspace = DASHBOARD_DIR.parent
    scripts_dir = workspace / 'scripts'
    report_path = _strategy_run_log_dir() / f'{run_id}_report.json'

    strategy_id = payload['strategy_id']
    task_type = payload['task_type']
    execute_mode = payload['execute_mode']

    if strategy_id == 'triple_screen':
        script_name = 'run_triple_screen_backfill.py' if task_type == 'backfill' else 'run_triple_screen_daily.py'
        exporter_script = scripts_dir / 'export_triple_screen_reports_pdf.py'
    else:
        script_name = 'run_neil_turtle_backfill.py' if task_type == 'backfill' else 'run_neil_turtle_daily.py'
        exporter_script = scripts_dir / 'export_neil_reports_pdf.py'

    script_path = scripts_dir / script_name
    if not script_path.exists():
        raise FileNotFoundError(f'strategy script not found: {script_path}')
    if not exporter_script.exists():
        raise FileNotFoundError(f'export script not found: {exporter_script}')

    command = ['python3', str(script_path), '--report', str(report_path)]
    if execute_mode == 'execute':
        command.append('--execute')
    if payload.get('as_of_date'):
        command.extend(['--as-of-date', str(payload['as_of_date'])])
    if payload.get('stock_codes'):
        command.extend(['--stock-codes', str(payload['stock_codes'])])

    return command, ['python3', str(exporter_script)], str(report_path)


def _strategy_run_default_artifacts(strategy_id: str):
    desktop = Path('/Users/mac/Desktop')
    if strategy_id == 'triple_screen':
        return [
            str(desktop / 'triple_screen_backfill_report.pdf'),
            str(desktop / 'triple_screen_daily_report.pdf'),
            str(desktop / 'triple_screen_backfill_report.md'),
            str(desktop / 'triple_screen_daily_report.md'),
        ]
    return [
        str(desktop / 'neil_turtle_backfill_report.pdf'),
        str(desktop / 'neil_turtle_daily_report.pdf'),
        str(desktop / 'neil_turtle_backfill_report.md'),
        str(desktop / 'neil_turtle_daily_report.md'),
    ]


def _run_strategy_job(run_id: str, payload: dict):
    """Execute strategy scripts synchronously and return run metadata updates."""
    command, exporter_command, report_path = _build_strategy_script_command(run_id, payload)
    log_path = _strategy_run_log_dir() / f'{run_id}.log'

    started_at = datetime.now().isoformat()
    result = subprocess.run(command, cwd=str(DASHBOARD_DIR.parent), text=True, capture_output=True)
    stdout_text = result.stdout or ''
    stderr_text = result.stderr or ''
    combined = []
    if stdout_text:
        combined.append(stdout_text.rstrip())
    if stderr_text:
        combined.append(stderr_text.rstrip())
    log_text = '\n\n'.join([x for x in combined if x]).strip()
    if log_text:
        log_path.write_text(log_text + '\n', encoding='utf-8')
    else:
        log_path.write_text('', encoding='utf-8')

    exporter_exit_code = None
    exporter_error = None
    if result.returncode == 0 and payload.get('export_pdf', True):
        exporter = subprocess.run(exporter_command, cwd=str(DASHBOARD_DIR.parent), text=True, capture_output=True)
        exporter_exit_code = int(exporter.returncode)
        exp_stdout = exporter.stdout or ''
        exp_stderr = exporter.stderr or ''
        if exp_stdout or exp_stderr:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write('\n===== EXPORTER =====\n')
                if exp_stdout:
                    f.write(exp_stdout.rstrip() + '\n')
                if exp_stderr:
                    f.write(exp_stderr.rstrip() + '\n')
        if exporter.returncode != 0:
            exporter_error = 'export_pdf failed'

    status = 'success'
    if result.returncode != 0 or exporter_error:
        status = 'failed'

    summary = {}
    report_file = Path(report_path)
    if report_file.exists():
        try:
            summary = json.loads(report_file.read_text(encoding='utf-8'))
        except Exception:
            summary = {}

    return {
        'status': status,
        'started_at': started_at,
        'finished_at': datetime.now().isoformat(),
        'command': command,
        'command_exit_code': int(result.returncode),
        'export_command': exporter_command if payload.get('export_pdf', True) else [],
        'export_exit_code': exporter_exit_code,
        'error': exporter_error or (stderr_text.strip()[:500] if result.returncode != 0 else None),
        'log_path': str(log_path),
        'report_path': str(report_file),
        'artifacts': _strategy_run_default_artifacts(payload['strategy_id']),
        'summary': summary if isinstance(summary, dict) else {},
    }


def _strategy_find_run(runs, run_id: str):
    for item in runs:
        if str(item.get('run_id')) == str(run_id):
            return item
    return None


@app.route('/api/strategy-runs', methods=['POST'])
def create_strategy_run():
    """Create and execute a strategy run (sync v1)."""
    try:
        payload = _normalize_strategy_run_input(request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'invalid request: {str(exc)}'}), 400

    run_id = uuid.uuid4().hex
    run = {
        'run_id': run_id,
        'status': 'queued',
        'requested_at': datetime.now().isoformat(),
        'strategy_id': payload['strategy_id'],
        'task_type': payload['task_type'],
        'execute_mode': payload['execute_mode'],
        'as_of_date': payload['as_of_date'],
        'stock_codes': payload['stock_codes'],
        'params': payload['params'],
        'export_pdf': bool(payload.get('export_pdf', True)),
    }

    with STRATEGY_RUNS_LOCK:
        runs = _load_strategy_runs_registry()
        runs.append(run)
        _save_strategy_runs_registry(runs)

    try:
        updates = _run_strategy_job(run_id, payload)
    except Exception as exc:
        updates = {
            'status': 'failed',
            'started_at': datetime.now().isoformat(),
            'finished_at': datetime.now().isoformat(),
            'command': [],
            'command_exit_code': None,
            'export_command': [],
            'export_exit_code': None,
            'error': str(exc),
            'log_path': None,
            'report_path': None,
            'artifacts': [],
            'summary': {},
        }

    with STRATEGY_RUNS_LOCK:
        runs = _load_strategy_runs_registry()
        target = _strategy_find_run(runs, run_id)
        if not target:
            target = run
            runs.append(target)
        target.update(updates)
        _save_strategy_runs_registry(runs)

    status_code = 200 if target.get('status') == 'success' else 500
    return safe_jsonify(target), status_code


@app.route('/api/strategy-runs/<run_id>', methods=['GET'])
def get_strategy_run(run_id: str):
    """Get strategy run detail by run_id."""
    with STRATEGY_RUNS_LOCK:
        runs = _load_strategy_runs_registry()
    item = _strategy_find_run(runs, run_id)
    if not item:
        return jsonify({'error': f'run not found: {run_id}'}), 404

    tail = request.args.get('tail', '')
    if tail:
        try:
            n = max(20, min(800, int(tail)))
        except Exception:
            n = 120
        log_path = item.get('log_path')
        item = dict(item)
        item['log_tail'] = _read_log_tail(Path(log_path), tail=n) if log_path else []
    return safe_jsonify(item)


@app.route('/api/strategy-runs', methods=['GET'])
def list_strategy_runs():
    """List strategy runs with lightweight filters and pagination."""
    strategy_id = str(request.args.get('strategy_id') or '').strip().lower()
    task_type = str(request.args.get('task_type') or '').strip().lower()
    status = str(request.args.get('status') or '').strip().lower()
    run_id = str(request.args.get('run_id') or '').strip()
    limit = _safe_int_arg('limit', 50, min_value=1, max_value=300)
    offset = _safe_int_arg('offset', 0, min_value=0, max_value=10000)

    if strategy_id and strategy_id not in ALLOWED_STRATEGY_IDS:
        return jsonify({'error': f'invalid strategy_id: {strategy_id}'}), 400
    if task_type and task_type not in ALLOWED_TASK_TYPES:
        return jsonify({'error': f'invalid task_type: {task_type}'}), 400

    with STRATEGY_RUNS_LOCK:
        runs = _load_strategy_runs_registry()

    filtered = []
    for item in runs:
        if not isinstance(item, dict):
            continue
        if run_id and str(item.get('run_id') or '') != run_id:
            continue
        if strategy_id and str(item.get('strategy_id') or '').lower() != strategy_id:
            continue
        if task_type and str(item.get('task_type') or '').lower() != task_type:
            continue
        if status and str(item.get('status') or '').lower() != status:
            continue
        filtered.append(item)

    def _filter_date_sort_key(item: dict):
        requested_key = str(item.get('requested_at') or '').strip()
        as_of = str(item.get('as_of_date') or '').strip()
        if as_of:
            date_key = as_of[:10]
        else:
            summary = item.get('summary') if isinstance(item.get('summary'), dict) else {}
            date_key = str(summary.get('target_trade_date') or '').strip()[:10]
        return (requested_key, date_key)

    filtered.sort(key=_filter_date_sort_key, reverse=True)

    total = len(filtered)
    page_items = filtered[offset : offset + limit]
    return safe_jsonify(
        {
            'items': page_items,
            'total': total,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total,
            'filters': {
                'run_id': run_id or None,
                'strategy_id': strategy_id or None,
                'task_type': task_type or None,
                'status': status or None,
            },
        }
    )


@app.route('/api/strategy-runs/<run_id>/logs', methods=['GET'])
def get_strategy_run_logs(run_id: str):
    """Get tail logs for a strategy run."""
    tail = _safe_int_arg('tail', 120, min_value=20, max_value=800)

    with STRATEGY_RUNS_LOCK:
        runs = _load_strategy_runs_registry()
    item = _strategy_find_run(runs, run_id)
    if not item:
        return jsonify({'error': f'run not found: {run_id}'}), 404

    log_path_raw = item.get('log_path')
    log_path = Path(str(log_path_raw)) if log_path_raw else None
    exists = bool(log_path and log_path.exists())
    lines = _read_log_tail(log_path, tail=tail) if exists else []
    return safe_jsonify(
        {
            'run_id': run_id,
            'tail': tail,
            'log_path': str(log_path) if log_path else None,
            'exists': exists,
            'lines': lines,
        }
    )


def _resolve_strategy_run_download_path(item: dict, kind: str) -> Path:
    kind = str(kind or '').strip().lower()
    if kind == 'report_json':
        report_path = item.get('report_path')
        if not report_path:
            raise FileNotFoundError('report file not found')
        return Path(str(report_path))
    if kind == 'log':
        log_path = item.get('log_path')
        if not log_path:
            raise FileNotFoundError('log file not found')
        return Path(str(log_path))

    strategy_id = str(item.get('strategy_id') or '').strip().lower()
    task_type = str(item.get('task_type') or '').strip().lower()
    if strategy_id == 'triple_screen':
        prefix = 'triple_screen'
    elif strategy_id == 'neil_turtle_short':
        prefix = 'neil_turtle'
    else:
        raise ValueError(f'unsupported strategy_id: {strategy_id}')

    if task_type not in {'daily', 'backfill'}:
        raise ValueError(f'unsupported task_type: {task_type}')

    suffix_map = {
        'pdf': 'pdf',
        'md': 'md',
    }
    ext = suffix_map.get(kind)
    if not ext:
        raise ValueError(f'unsupported download kind: {kind}')

    desktop = Path('/Users/mac/Desktop')
    return desktop / f'{prefix}_{task_type}_report.{ext}'


@app.route('/api/strategy-runs/<run_id>/download', methods=['GET'])
def download_strategy_run_artifact(run_id: str):
    kind = str(request.args.get('kind') or 'report_json').strip().lower()
    with STRATEGY_RUNS_LOCK:
        runs = _load_strategy_runs_registry()
    item = _strategy_find_run(runs, run_id)
    if not item:
        return jsonify({'error': f'run not found: {run_id}'}), 404

    try:
        path = _resolve_strategy_run_download_path(item, kind)
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    if not path.exists() or not path.is_file():
        return jsonify({'error': f'file not found: {path}'}), 404

    allowed_roots = [
        (DASHBOARD_DIR.parent / 'logs').resolve(),
        Path('/Users/mac/Desktop').resolve(),
    ]
    resolved = path.resolve()
    if not any(str(resolved).startswith(str(root)) for root in allowed_roots):
        return jsonify({'error': 'forbidden file path'}), 403

    return send_file(str(resolved), as_attachment=True, download_name=resolved.name)


V4_LAB_OUTPUT_DIR = DASHBOARD_DIR.parent / 'research' / 'v4_trend_research' / 'output'
V4_LAB_THEME_KEYWORDS = {
    'AiDC': ['AI', 'AIDC', '算力', '数据中心', '智算', '服务器', '云计算', '人工智能', '半导体', '信息产业', '软件和信息技术服务业'],
    '绿能新能': ['绿能', '新能源', '光伏', '风电', '氢能', '电池', '电气设备', '电力设备'],
    '算电结合': ['算电', '电力设备', '电网', '特高压', 'IDC电源', '液冷', '电气设备'],
    '国产替代': ['国产替代', '自主可控', '信创', '半导体', '国产化'],
    '储能': ['储能', '锂电', '电化学储能', '逆变器', '电池', '电气设备'],
    '新型医药': ['创新药', '医药', '生物医药', '医疗器械', 'CXO', '中药', '化学制药', '医药制造业'],
}


def _v4_lab_read_csv_rows(path: Path):
    if not path.exists() or not path.is_file():
        return []
    rows = []
    with path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _v4_lab_to_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _v4_lab_to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _v4_lab_latest_snapshot_mtime():
    paths = [
        V4_LAB_OUTPUT_DIR / 'v4_2_dynamic_hardened_candidate_latest.json',
        V4_LAB_OUTPUT_DIR / 'v4_2_dynamic_candidate_latest.json',
    ]
    mtimes = [p.stat().st_mtime for p in paths if p.exists()]
    if not mtimes:
        return None
    return datetime.fromtimestamp(max(mtimes)).isoformat()


def _v4_lab_cluster_fn(desc: str):
    d = str(desc or '').replace(' ', '')
    if d == 'rim<=58':
        return lambda x: _v4_lab_to_float(x.get('rim_interval'), 0.0) <= 58
    if d == 'rim<=70&cup>0.12':
        return lambda x: _v4_lab_to_float(x.get('rim_interval'), 0.0) <= 70 and _v4_lab_to_float(x.get('cup_depth'), 0.0) > 0.12
    if d == 'rim<=70&cup>0.15':
        return lambda x: _v4_lab_to_float(x.get('rim_interval'), 0.0) <= 70 and _v4_lab_to_float(x.get('cup_depth'), 0.0) > 0.15
    if d == 'rim<=80&0.15<cup<=0.30':
        return lambda x: _v4_lab_to_float(x.get('rim_interval'), 0.0) <= 80 and 0.15 < _v4_lab_to_float(x.get('cup_depth'), 0.0) <= 0.30
    if d == '58<rim<=91&0.15<cup<=0.30':
        return lambda x: 58 < _v4_lab_to_float(x.get('rim_interval'), 0.0) <= 91 and 0.15 < _v4_lab_to_float(x.get('cup_depth'), 0.0) <= 0.30
    if d == 'rim<=70&amount<=2.13&cup>0.16':
        return lambda x: _v4_lab_to_float(x.get('rim_interval'), 0.0) <= 70 and _v4_lab_to_float(x.get('amount_ratio'), 0.0) <= 2.13 and _v4_lab_to_float(x.get('cup_depth'), 0.0) > 0.16
    if d == 'amount<=2.13':
        return lambda x: _v4_lab_to_float(x.get('amount_ratio'), 0.0) <= 2.13
    return lambda _x: False


def _v4_lab_compute_market_state(target_date: str):
    # Same rules as prototype_v4_2_phaseA_minimal.py
    if not target_date:
        return {'market_state': 'S2_neutral'}
    conn = get_stock_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT trade_date
            FROM daily_prices
            WHERE trade_date <= ?
            ORDER BY trade_date DESC
            LIMIT 20
            """,
            (target_date,),
        )
        dates = [str((r['trade_date'] if isinstance(r, dict) else r[0]) or '') for r in cur.fetchall()]
        dates = sorted([d for d in dates if d])
        if not dates:
            return {'market_state': 'S2_neutral'}

        metrics = {}
        for d in dates:
            cur.execute(
                """
                SELECT pct_change
                FROM daily_prices
                WHERE trade_date = ? AND pct_change IS NOT NULL
                """,
                (d,),
            )
            vals = [float((x['pct_change'] if isinstance(x, dict) else x[0]) or 0.0) for x in cur.fetchall()]
            if not vals:
                continue
            up_ratio = sum(1 for x in vals if x > 0) / len(vals)
            mean_pct = sum(vals) / len(vals)
            if len(vals) > 1:
                m = mean_pct
                var = sum((x - m) ** 2 for x in vals) / len(vals)
                disp_pct = math.sqrt(max(var, 0.0))
            else:
                disp_pct = 0.0
            metrics[d] = {'up_ratio': up_ratio, 'mean_pct': mean_pct, 'disp_pct': disp_pct}

        valid_dates = sorted(metrics.keys())
        if not valid_dates:
            return {'market_state': 'S2_neutral'}
        up = [metrics[d]['up_ratio'] for d in valid_dates]
        mp = [metrics[d]['mean_pct'] for d in valid_dates]
        dp = [metrics[d]['disp_pct'] for d in valid_dates]

        def _rolling_mean(vals, i, window):
            lo = max(0, i - window + 1)
            seg = vals[lo:i + 1]
            return (sum(seg) / len(seg)) if seg else 0.0

        i = len(valid_dates) - 1
        up5 = _rolling_mean(up, i, 5)
        up20 = _rolling_mean(up, i, 20)
        mp5 = _rolling_mean(mp, i, 5)
        mp20 = _rolling_mean(mp, i, 20)
        dp5 = _rolling_mean(dp, i, 5)
        dp20 = _rolling_mean(dp, i, 20)
        if up5 >= up20 and mp5 > mp20 and dp5 <= max(dp20, 1e-9) * 1.10:
            st = 'S1_risk_on'
        elif up5 < up20 and mp5 < mp20:
            st = 'S3_risk_off'
        else:
            st = 'S2_neutral'
        return {
            'market_state': st,
            'up_ratio_ma5': up5,
            'up_ratio_ma20': up20,
            'mean_pct_ma5': mp5,
            'mean_pct_ma20': mp20,
            'disp_pct_ma5': dp5,
            'disp_pct_ma20': dp20,
        }
    finally:
        conn.close()


def _v4_lab_eval_success_t8(stock_code: str, signal_date: str, strength=0.04, drawdown=0.03, up_days_min=5):
    conn = get_stock_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT trade_date, close
            FROM daily_prices
            WHERE code = ? AND trade_date >= ? AND close IS NOT NULL
            ORDER BY trade_date ASC
            LIMIT 9
            """,
            (stock_code, signal_date),
        )
        rows = cur.fetchall()
        if not rows:
            return {'ready': False, 'reason': 'no_price_data'}
        closes = [float((r['close'] if isinstance(r, dict) else r[1]) or 0.0) for r in rows]
        if not closes or closes[0] <= 0:
            return {'ready': False, 'reason': 'bad_t0_close'}
        if len(closes) < 9:
            return {'ready': False, 'reason': 'insufficient_forward_bars', 'ready_days': max(len(closes) - 1, 0)}
        close_t0 = closes[0]
        returns = [(c / close_t0) - 1.0 for c in closes[1:9]]
        end_return = returns[-1]
        drawdown_mag = max(0.0, -min(returns)) if returns else 0.0
        up_days = sum(1 for x in returns if x > 0)
        ok = (end_return >= strength) and (drawdown_mag <= drawdown) and (up_days >= up_days_min) and (end_return > 0.0)
        return {
            'ready': True,
            'is_success_strict': 1 if ok else 0,
            'end_return_t8': end_return,
            'drawdown_mag_t1_t8': drawdown_mag,
            'up_days_t1_t8': up_days,
            'spec': {'strength': strength, 'drawdown': drawdown, 'up_days_min': up_days_min},
        }
    finally:
        conn.close()


@app.route('/api/cup-handle-lab/summary', methods=['GET'])
def cup_handle_lab_summary():
    """
    Cup-handle lab summary for UI:
    - latest version and publish time
    - overall/base success rates
    - per-state success rates
    - recent 4-week trend (daily summary rolling)
    """
    overall_rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_replay_overall_summary.csv')
    if not overall_rows:
        return jsonify({'error': 'cup-handle summary not ready'}), 404

    overall_map = {str(r.get('bucket') or ''): r for r in overall_rows}
    all_row = overall_map.get('ALL') or {}

    hardened_snapshot_path = V4_LAB_OUTPUT_DIR / 'v4_2_dynamic_hardened_candidate_latest.json'
    hardened_snapshot = {}
    if hardened_snapshot_path.exists():
        try:
            hardened_snapshot = json.loads(hardened_snapshot_path.read_text(encoding='utf-8'))
        except Exception:
            hardened_snapshot = {}

    base_rate = None
    hardening_result = hardened_snapshot.get('hardening', {}).get('result', {})
    if isinstance(hardening_result, dict):
        base_rate = _v4_lab_to_float(hardening_result.get('total_success_rate', 0.0), 0.0)

    # Prefer numeric evidence from daily diff file
    diff_daily_rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_base_hardened_daily_diff.csv')
    if diff_daily_rows:
        base_n = sum(_v4_lab_to_int(r.get('base_n'), 0) for r in diff_daily_rows)
        base_s = sum(_v4_lab_to_int(r.get('base_success'), 0) for r in diff_daily_rows)
        if base_n > 0:
            base_rate = base_s / base_n

    daily_rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_replay_daily_summary.csv')
    daily_rows.sort(key=lambda r: str(r.get('signal_date') or ''))
    recent = daily_rows[-20:] if len(daily_rows) > 20 else daily_rows
    weekly = []
    if recent:
        for i in range(0, len(recent), 5):
            chunk = recent[i : i + 5]
            n = sum(_v4_lab_to_int(r.get('pick_n'), 0) for r in chunk)
            s = sum(_v4_lab_to_int(r.get('success_n'), 0) for r in chunk)
            weekly.append(
                {
                    'window': f"W{len(weekly) + 1}",
                    'pick_n': n,
                    'success_n': s,
                    'success_rate': (s / n) if n else 0.0,
                }
            )

    return safe_jsonify(
        {
            'meta': {
                'latest_snapshot_detected_at': _v4_lab_latest_snapshot_mtime(),
                'latest_hardened_version': hardened_snapshot.get('candidate_version'),
                'latest_hardened_published_at': hardened_snapshot.get('published_at'),
            },
            'quality': {
                'hardened_success_rate': _v4_lab_to_float(all_row.get('success_rate'), 0.0),
                'hardened_pick_n': _v4_lab_to_int(all_row.get('pick_n'), 0),
                'hardened_success_n': _v4_lab_to_int(all_row.get('success_n'), 0),
                'base_success_rate': base_rate,
                'delta_vs_base': (
                    _v4_lab_to_float(all_row.get('success_rate'), 0.0) - float(base_rate)
                    if base_rate is not None
                    else None
                ),
            },
            'states': [
                {
                    'state': 'S1_risk_on',
                    'success_rate': _v4_lab_to_float((overall_map.get('S1_risk_on') or {}).get('success_rate'), 0.0),
                    'pick_n': _v4_lab_to_int((overall_map.get('S1_risk_on') or {}).get('pick_n'), 0),
                },
                {
                    'state': 'S2_neutral',
                    'success_rate': _v4_lab_to_float((overall_map.get('S2_neutral') or {}).get('success_rate'), 0.0),
                    'pick_n': _v4_lab_to_int((overall_map.get('S2_neutral') or {}).get('pick_n'), 0),
                },
                {
                    'state': 'S3_risk_off',
                    'success_rate': _v4_lab_to_float((overall_map.get('S3_risk_off') or {}).get('success_rate'), 0.0),
                    'pick_n': _v4_lab_to_int((overall_map.get('S3_risk_off') or {}).get('pick_n'), 0),
                },
            ],
            'trend_4w': weekly[-4:] if weekly else [],
            'self_explanatory': {
                'goal': '提升候选股票在未来数日内进入上行启动段的概率',
                'method': 'V4 与 V4.2 并行对照，持续回放与样本外验证，稳健后小步迭代',
                'note': '当前指标用于研究指导，不是交易指令',
            },
        }
    )


@app.route('/api/cup-handle-lab/daily', methods=['GET'])
def cup_handle_lab_daily():
    limit = _safe_int_arg('limit', 60, min_value=10, max_value=400)
    rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_replay_daily_summary.csv')
    rows.sort(key=lambda r: str(r.get('signal_date') or ''), reverse=True)
    page = rows[:limit]
    out = []
    for r in page:
        out.append(
            {
                'signal_date': r.get('signal_date'),
                'market_state': r.get('market_state'),
                'cluster_desc': r.get('cluster_desc'),
                'pick_n': _v4_lab_to_int(r.get('pick_n'), 0),
                'success_n': _v4_lab_to_int(r.get('success_n'), 0),
                'success_rate': _v4_lab_to_float(r.get('success_rate'), 0.0),
                'avg_dynamic_score': _v4_lab_to_float(r.get('avg_dynamic_score'), 0.0),
                'avg_end_return_t8': _v4_lab_to_float(r.get('avg_end_return_t8'), 0.0),
            }
        )
    return safe_jsonify({'items': out, 'total': len(rows), 'limit': limit})


@app.route('/api/cup-handle-lab/stocks', methods=['GET'])
def cup_handle_lab_stocks():
    limit = _safe_int_arg('limit', 120, min_value=20, max_value=600)
    entry_filter = (request.args.get('entry') or '').strip()
    state_filter = (request.args.get('state') or '').strip()
    latest_only = _safe_int_arg('latest_only', -1, min_value=-1, max_value=1)
    signal_date_filter = (request.args.get('signal_date') or '').strip()
    preferred_themes_raw = (request.args.get('preferred_themes') or '').strip()
    theme_mode = (request.args.get('theme_mode') or 'off').strip().lower()
    if theme_mode not in ('off', 'prefer', 'only'):
        theme_mode = 'off'
    preferred_themes = [x.strip() for x in preferred_themes_raw.split(',') if x.strip() in V4_LAB_THEME_KEYWORDS]

    rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_replay_daily_pool.csv')
    if not rows:
        return safe_jsonify({'items': [], 'total': 0, 'limit': limit, 'meta': {'latest_signal_date': None, 'sort_rule': 'estimated_win_rate_desc'}})

    # Hist stats for estimating "currently expected win-rate" by entry/state profile.
    hist_profile = {}
    hist_entry = {}
    hist_state = {}
    latest_signal_date = max(str(r.get('signal_date') or '') for r in rows)
    for r in rows:
        state = str(r.get('market_state') or '')
        entry_id = str(r.get('cluster_id') or '')
        seg = str(r.get('segment_id') or '')
        succ = _v4_lab_to_int(r.get('is_success_strict'), 0)

        k_profile = (state, entry_id, seg)
        k_entry = (state, entry_id)
        for bag, key in ((hist_profile, k_profile), (hist_entry, k_entry), (hist_state, state)):
            cur = bag.get(key) or {'n': 0, 's': 0}
            cur['n'] += 1
            cur['s'] += succ
            bag[key] = cur

    all_dates = sorted({str(r.get('signal_date') or '') for r in rows if str(r.get('signal_date') or '')})

    # History stats for monitoring pool: by stock_code, aggregate across all available replay dates.
    # We treat one "cup occurrence" as one signal_date for a stock (may have multiple entry rows).
    hist_by_code = {}
    if rows:
        by_code_date = {}
        for r in rows:
            d = str(r.get('signal_date') or '').strip()
            code = str(r.get('stock_code') or '').strip()
            if not d or not code:
                continue
            raw_s = r.get('is_success_strict')
            succ_val = None
            if raw_s is not None and str(raw_s).strip() != '':
                succ_val = 1 if _v4_lab_to_int(raw_s, 0) == 1 else 0
            key = (code, d)
            prev = by_code_date.get(key)
            if prev is None:
                by_code_date[key] = {'succ': succ_val}
            else:
                # Promote to success if any entry row on that date is success.
                if succ_val == 1:
                    prev['succ'] = 1
                elif prev.get('succ') is None and succ_val == 0:
                    prev['succ'] = 0

        by_code = {}
        for (code, d), v in by_code_date.items():
            bucket = by_code.get(code)
            if not bucket:
                bucket = {'dates': set(), 'ready_n': 0, 'succ_n': 0}
                by_code[code] = bucket
            bucket['dates'].add(d)
            succ = v.get('succ')
            if succ in (0, 1):
                bucket['ready_n'] += 1
                if succ == 1:
                    bucket['succ_n'] += 1

        for code, bucket in by_code.items():
            ready_n = int(bucket.get('ready_n') or 0)
            succ_n = int(bucket.get('succ_n') or 0)
            cup_n = len(bucket.get('dates') or set())
            hist_by_code[code] = {
                'history_cup_n': cup_n,
                'history_ready_n': ready_n,
                'history_success_n': succ_n,
                'history_success_rate': (succ_n / ready_n) if ready_n > 0 else None,
                'history_has_success': (succ_n > 0),
            }

    # Hard constraint: V4.2 can only operate within V4 base pool.
    v4_map_by_date = {}
    if all_dates:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            placeholders = ','.join(['?'] * len(all_dates))
            cur.execute(
                f"""
                SELECT rr.run_date, sr.stock_code
                FROM screener_runs rr
                JOIN screener_results sr ON sr.run_id = rr.id
                WHERE rr.screener_name = ? AND rr.status = 'completed' AND rr.run_date IN ({placeholders})
                """,
                tuple(['coffee_cup_v4'] + all_dates),
            )
            for row in cur.fetchall():
                run_date = str(row[0] or '')
                code = str(row[1] or '').strip()
                if not run_date or not code:
                    continue
                bag = v4_map_by_date.get(run_date) or set()
                bag.add(code)
                v4_map_by_date[run_date] = bag
        finally:
            conn.close()

    v4_missing_baseline_dates = set()
    def _in_v4_pool(_r):
        d = str(_r.get('signal_date') or '')
        code = str(_r.get('stock_code') or '').strip()
        if not d or not code:
            return False
        bag = v4_map_by_date.get(d)
        if not bag:
            # Replay pool may contain dates that do not have a completed V4 run in dashboard.db
            # (e.g. because V4 is run on trading days while replay uses label-ready dates).
            # In this case, do not drop all rows; allow them through and surface the gap in meta.
            v4_missing_baseline_dates.add(d)
            return True
        return code in bag

    def _row_match_basic(_r):
        if state_filter and str(_r.get('market_state') or '') != state_filter:
            return False
        if entry_filter and str(_r.get('cluster_id') or '') != entry_filter:
            return False
        return True

    used_dates = set()
    window_mode = 'adaptive_recent'
    window_days = 0
    if signal_date_filter:
        used_dates = {signal_date_filter} if signal_date_filter in all_dates else set()
        window_mode = 'explicit_date'
        window_days = 1
    elif latest_only == 1:
        used_dates = {latest_signal_date}
        window_mode = 'latest_only'
        window_days = 1
    elif latest_only == 0:
        n = _safe_int_arg('window_days', 20, min_value=5, max_value=120)
        used_dates = set(all_dates[-n:])
        window_mode = 'fixed_recent'
        window_days = n
    else:
        # Default adaptive mode: avoid displaying too few stocks when latest day is sparse.
        used_dates = {latest_signal_date}
        latest_rows = [r for r in rows if str(r.get('signal_date') or '') == latest_signal_date and _row_match_basic(r) and _in_v4_pool(r)]
        latest_stock_n = len({str(r.get('stock_code') or '').strip() for r in latest_rows if str(r.get('stock_code') or '').strip()})
        if latest_stock_n < 20:
            n = 20
            while n <= 60:
                date_set = set(all_dates[-n:])
                sub = [r for r in rows if str(r.get('signal_date') or '') in date_set and _row_match_basic(r) and _in_v4_pool(r)]
                stock_n = len({str(r.get('stock_code') or '').strip() for r in sub if str(r.get('stock_code') or '').strip()})
                used_dates = date_set
                window_days = n
                if stock_n >= 20:
                    break
                n += 10
        else:
            window_days = 1

    src_rows = []
    candidate_rows_after_basic_filter = 0
    filtered_out_not_in_v4 = 0
    for r in rows:
        signal_date = str(r.get('signal_date') or '')
        if signal_date not in used_dates:
            continue
        if not _row_match_basic(r):
            continue
        candidate_rows_after_basic_filter += 1
        if not _in_v4_pool(r):
            filtered_out_not_in_v4 += 1
            continue
        src_rows.append(r)

    grouped = {}
    for r in src_rows:
        code = str(r.get('stock_code') or '').strip()
        if not code:
            continue
        name = str(r.get('stock_name') or '').strip()
        state = str(r.get('market_state') or '')
        entry_id = str(r.get('cluster_id') or '')
        entry_desc = str(r.get('cluster_desc') or '')
        seg = str(r.get('segment_id') or '')
        signal_date = str(r.get('signal_date') or '')
        dyn = _v4_lab_to_float(r.get('dynamic_score'), 0.0)
        raw_succ = r.get('is_success_strict')
        succ_val = None
        if raw_succ is not None and str(raw_succ).strip() != '':
            succ_val = 1 if _v4_lab_to_int(raw_succ, 0) == 1 else 0
        end_ret_t8 = None
        raw_ret = r.get('end_return_t8')
        if raw_ret is not None and str(raw_ret).strip() != '':
            try:
                end_ret_t8 = float(raw_ret)
            except Exception:
                end_ret_t8 = None
        drawdown_t1_t8 = None
        raw_dd = r.get('drawdown_mag_t1_t8')
        if raw_dd is not None and str(raw_dd).strip() != '':
            try:
                drawdown_t1_t8 = float(raw_dd)
            except Exception:
                drawdown_t1_t8 = None

        p = hist_profile.get((state, entry_id, seg)) or {'n': 0, 's': 0}
        e = hist_entry.get((state, entry_id)) or {'n': 0, 's': 0}
        s = hist_state.get(state) or {'n': 0, 's': 0}
        if p['n'] > 0:
            est = p['s'] / p['n']
            confidence = p['n']
        elif e['n'] > 0:
            est = e['s'] / e['n']
            confidence = e['n']
        else:
            est = (s['s'] / s['n']) if s['n'] > 0 else 0.0
            confidence = s['n']

        entry_item = {
            'entry_id': entry_id,
            'entry_desc': entry_desc,
            'market_state': state,
            'segment_id': seg,
            'signal_date': signal_date,
            'dynamic_score': dyn,
            'is_success_strict': succ_val,
            'end_return_t8': end_ret_t8,
            'drawdown_mag_t1_t8': drawdown_t1_t8,
            'estimated_win_rate': est,
            'sample_n': confidence,
            'reason_tags': [
                f"入口:{entry_id or '-'}",
                f"状态:{state or '-'}",
                f"分型:{seg or '-'}",
                f"评分:{dyn:.2f}",
            ],
        }

        cur = grouped.get(code)
        if not cur:
            h = hist_by_code.get(code) or {}
            cur = {
                'stock_code': code,
                'stock_name': name,
                'signal_date': signal_date,
                'estimated_win_rate': est,
                'dynamic_score': dyn,
                'sample_n': confidence,
                'entry_count': 0,
                'entries': [],
                'reason_tags': [],
                'is_success_strict': succ_val,
                'end_return_t8': end_ret_t8,
                'drawdown_mag_t1_t8': drawdown_t1_t8,
                'history_cup_n': h.get('history_cup_n'),
                'history_ready_n': h.get('history_ready_n'),
                'history_success_n': h.get('history_success_n'),
                'history_success_rate': h.get('history_success_rate'),
                'history_has_success': h.get('history_has_success'),
            }
            grouped[code] = cur
        else:
            if succ_val == 1:
                cur['is_success_strict'] = 1
            if cur.get('is_success_strict') is None and succ_val == 0:
                cur['is_success_strict'] = 0
            if end_ret_t8 is not None:
                prev = cur.get('end_return_t8')
                try:
                    prev_f = float(prev) if prev is not None else None
                except Exception:
                    prev_f = None
                if prev_f is None or end_ret_t8 > prev_f:
                    cur['end_return_t8'] = end_ret_t8
            if drawdown_t1_t8 is not None:
                prev = cur.get('drawdown_mag_t1_t8')
                try:
                    prev_f = float(prev) if prev is not None else None
                except Exception:
                    prev_f = None
                if prev_f is None or drawdown_t1_t8 > prev_f:
                    cur['drawdown_mag_t1_t8'] = drawdown_t1_t8

        cur['entries'].append(entry_item)
        cur['entry_count'] = len(cur['entries'])
        # Keep best-confidence/best-win entry as stock primary view.
        if (
            est > float(cur.get('estimated_win_rate') or 0.0)
            or (abs(est - float(cur.get('estimated_win_rate') or 0.0)) < 1e-12 and dyn > float(cur.get('dynamic_score') or 0.0))
        ):
            cur['estimated_win_rate'] = est
            cur['dynamic_score'] = dyn
            cur['sample_n'] = confidence
            cur['signal_date'] = signal_date
            cur['reason_tags'] = entry_item['reason_tags']

    items = []
    for _code, item in grouped.items():
        item['entries'].sort(key=lambda x: (float(x.get('estimated_win_rate') or 0.0), float(x.get('dynamic_score') or 0.0)), reverse=True)
        if not item['reason_tags'] and item['entries']:
            item['reason_tags'] = item['entries'][0].get('reason_tags') or []
        items.append(item)

    # Attach industry/sector metadata to support human theme-bias constraints.
    meta_map = {}
    code_list = [str(x.get('stock_code') or '') for x in items if str(x.get('stock_code') or '')]
    if code_list:
        stock_db_path = DASHBOARD_DIR.parent / 'data' / 'stock_data.db'
        if stock_db_path.exists():
            try:
                conn_meta = sqlite3.connect(stock_db_path)
                conn_meta.row_factory = sqlite3.Row
                cur_meta = conn_meta.cursor()
                placeholders = ','.join(['?'] * len(code_list))
                cur_meta.execute(
                    f"""
                    SELECT code, COALESCE(industry, '') AS industry, COALESCE(sector_lv1, '') AS sector_lv1, COALESCE(sector_lv2, '') AS sector_lv2
                    FROM stock_meta
                    WHERE code IN ({placeholders})
                    """,
                    tuple(code_list),
                )
                for r in cur_meta.fetchall():
                    meta_map[str(r['code'])] = {
                        'industry': str(r['industry'] or ''),
                        'sector_lv1': str(r['sector_lv1'] or ''),
                        'sector_lv2': str(r['sector_lv2'] or ''),
                    }
                conn_meta.close()
            except Exception:
                # Metadata is optional. Keep API stable even if stock_meta is unavailable.
                meta_map = {}

    def _match_themes(industry: str, s1: str, s2: str):
        text = f"{industry}|{s1}|{s2}".lower()
        matched = []
        for theme, words in V4_LAB_THEME_KEYWORDS.items():
            for w in words:
                if str(w).lower() in text:
                    matched.append(theme)
                    break
        return matched

    for item in items:
        code = str(item.get('stock_code') or '')
        m = meta_map.get(code) or {}
        industry = str(m.get('industry') or '')
        s1 = str(m.get('sector_lv1') or '')
        s2 = str(m.get('sector_lv2') or '')
        matched = _match_themes(industry, s1, s2)
        item['industry'] = industry
        item['sector_lv1'] = s1
        item['sector_lv2'] = s2
        item['matched_themes'] = matched
        item['theme_hit_n'] = len(matched)

    if preferred_themes and theme_mode == 'only':
        preferred_set = set(preferred_themes)
        items = [x for x in items if preferred_set.intersection(set(x.get('matched_themes') or []))]

    if preferred_themes and theme_mode == 'prefer':
        preferred_set = set(preferred_themes)
        items.sort(
            key=lambda x: (
                1 if preferred_set.intersection(set(x.get('matched_themes') or [])) else 0,
                int(x.get('theme_hit_n') or 0),
                float(x.get('estimated_win_rate') or 0.0),
                float(x.get('dynamic_score') or 0.0),
                int(x.get('sample_n') or 0),
            ),
            reverse=True,
        )
    else:
        items.sort(
            key=lambda x: (
                float(x.get('estimated_win_rate') or 0.0),
                float(x.get('dynamic_score') or 0.0),
                int(x.get('sample_n') or 0),
            ),
            reverse=True,
        )

    # Entry-level summary window source
    entry_map = {}
    for r in src_rows:
        k = str(r.get('cluster_id') or '')
        cur = entry_map.get(k) or {
            'entry_id': k,
            'entry_desc': str(r.get('cluster_desc') or ''),
            'pick_n': 0,
            'avg_dynamic_score': 0.0,
            '_dyn_sum': 0.0,
            '_est_sum': 0.0,
            '_n': 0,
        }
        state = str(r.get('market_state') or '')
        seg = str(r.get('segment_id') or '')
        p = hist_profile.get((state, k, seg)) or {'n': 0, 's': 0}
        est = (p['s'] / p['n']) if p['n'] > 0 else 0.0
        cur['pick_n'] += 1
        cur['_dyn_sum'] += _v4_lab_to_float(r.get('dynamic_score'), 0.0)
        cur['_est_sum'] += est
        cur['_n'] += 1
        entry_map[k] = cur

    entry_windows = []
    for _k, v in entry_map.items():
        n = v['_n'] or 1
        entry_windows.append(
            {
                'entry_id': v['entry_id'],
                'entry_desc': v['entry_desc'],
                'pick_n': int(v['pick_n']),
                'avg_dynamic_score': float(v['_dyn_sum']) / n,
                'estimated_win_rate': float(v['_est_sum']) / n,
            }
        )
    entry_windows.sort(key=lambda x: (float(x.get('estimated_win_rate') or 0.0), int(x.get('pick_n') or 0)), reverse=True)

    v4_missing_dates = sorted({d for d in used_dates if not (v4_map_by_date.get(d) or set())})
    v4_available_dates_n = len(set(used_dates) - set(v4_missing_dates))
    source_mode = 'v4_pool_only' if not v4_missing_dates else 'v4_pool_if_available'

    return safe_jsonify(
        {
            'items': items[:limit],
            'total': len(items),
            'limit': limit,
            'meta': {
                'latest_signal_date': latest_signal_date,
                'sort_rule': 'estimated_win_rate_desc_then_dynamic_score_desc',
                'window_mode': window_mode,
                'window_days': window_days,
                'used_date_count': len(used_dates),
                'requested_signal_date': signal_date_filter or None,
                'available_signal_dates': all_dates[-240:],
                'theme_mode': theme_mode,
                'preferred_themes': preferred_themes,
                'theme_catalog': list(V4_LAB_THEME_KEYWORDS.keys()),
                'source_mode': source_mode,
                'excluded_not_in_v4_n': filtered_out_not_in_v4,
                'v4_pool_total_n': sum(len(v4_map_by_date.get(d) or set()) for d in used_dates),
                'v42_candidate_rows_n': candidate_rows_after_basic_filter,
                'v42_rows_in_v4_n': len(src_rows),
                'v4_baseline_missing_dates': v4_missing_dates,
                'v4_baseline_missing_dates_n': len(v4_missing_dates),
                'v4_baseline_available_dates_n': v4_available_dates_n,
            },
            'entry_windows': entry_windows,
        }
    )


@app.route('/api/cup-handle-lab/alignment', methods=['GET'])
def cup_handle_lab_alignment():
    """
    Same-date V4 vs V4.2 objective alignment check.
    - V4 set: screener_results from coffee_cup_v4 completed run on date D.
    - V4.2 base set: v4_2_replay_daily_pool.csv rows on date D.
    - V4.2 hardened set: base set minus removed_by_hardening rows from stock diff on D.
    """
    req_date = (request.args.get('date') or '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT run_date, stocks_found
        FROM screener_runs
        WHERE screener_name = ? AND status = 'completed'
        ORDER BY run_date
        """,
        ('coffee_cup_v4',),
    )
    v4_rows = cursor.fetchall()
    v4_count_by_date = {}
    for row in v4_rows:
        d = str(row[0]) if row and row[0] else ''
        if not d:
            continue
        n = _v4_lab_to_int(row[1], 0)
        if d not in v4_count_by_date or n > v4_count_by_date[d]:
            v4_count_by_date[d] = n
    v4_dates = sorted(v4_count_by_date.keys())

    base_rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_replay_daily_pool.csv')
    v42_dates = sorted({str(r.get('signal_date') or '') for r in base_rows if str(r.get('signal_date') or '')})
    common_dates = sorted(set(v4_dates).intersection(set(v42_dates)))

    base_count_by_date = {}
    for r in base_rows:
        d = str(r.get('signal_date') or '')
        code = str(r.get('stock_code') or '').strip()
        if not d or not code:
            continue
        if d not in base_count_by_date:
            base_count_by_date[d] = set()
        base_count_by_date[d].add(code)

    diff_rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_base_hardened_stock_diff.csv')
    removed_by_date = {}
    for r in diff_rows:
        if str(r.get('change_type') or '') != 'removed_by_hardening':
            continue
        d = str(r.get('signal_date') or '')
        code = str(r.get('stock_code') or '').strip()
        if not d or not code:
            continue
        if d not in removed_by_date:
            removed_by_date[d] = set()
        removed_by_date[d].add(code)

    candidate_dates = []
    for d in common_dates:
        v4_n = int(v4_count_by_date.get(d, 0))
        base_set = base_count_by_date.get(d, set())
        hard_set = set(base_set) - set(removed_by_date.get(d, set()))
        if v4_n > 0 and len(base_set) > 0:
            candidate_dates.append(
                {
                    'date': d,
                    'v4_count': v4_n,
                    'v42_base_count': len(base_set),
                    'v42_hardened_count': len(hard_set),
                }
            )

    target_date = req_date if req_date else (candidate_dates[-1]['date'] if candidate_dates else (common_dates[-1] if common_dates else ''))
    candidate_date_set = {x['date'] for x in candidate_dates}
    if req_date and req_date not in candidate_date_set:
        conn.close()
        return safe_jsonify(
            {
                'error': 'Requested date has no valid same-day alignment data',
                'requested_date': req_date,
                'meta': {
                    'latest_v4_date': (v4_dates[-1] if v4_dates else None),
                    'latest_v42_date': (v42_dates[-1] if v42_dates else None),
                    'latest_common_date': (common_dates[-1] if common_dates else None),
                    'candidate_dates': candidate_dates[-40:],
                },
            }
        ), 400

    if not target_date:
        conn.close()
        return safe_jsonify(
            {
                'meta': {
                    'latest_v4_date': (v4_dates[-1] if v4_dates else None),
                    'latest_v42_date': (v42_dates[-1] if v42_dates else None),
                    'latest_common_date': None,
                    'candidate_dates': [],
                },
                'counts': {
                    'v4_count': 0,
                    'v42_base_count': 0,
                    'v42_hardened_count': 0,
                    'overlap_base_count': 0,
                    'overlap_hardened_count': 0,
                },
                'ratios': {
                    'hardened_vs_v4': 0.0,
                    'hardened_vs_base': 0.0,
                    'base_vs_v4': 0.0,
                },
                'quality': {
                    'base_success_rate': 0.0,
                    'hardened_success_rate': 0.0,
                    'delta_success_rate': 0.0,
                },
                'warnings': ['No common dates between V4 run data and V4.2 replay data'],
                'samples': {'only_v4': [], 'only_v42_hardened': [], 'intersection_hardened': []},
            }
        )

    cursor.execute(
        """
        SELECT id FROM screener_runs
        WHERE screener_name = ? AND run_date = ? AND status = 'completed'
        ORDER BY id DESC LIMIT 1
        """,
        ('coffee_cup_v4', target_date),
    )
    run_row = cursor.fetchone()
    v4_items = []
    if run_row and run_row[0]:
        run_id = int(run_row[0])
        cursor.execute(
            "SELECT stock_code, stock_name FROM screener_results WHERE run_id = ?",
            (run_id,),
        )
        v4_items = [{'stock_code': str(r[0]), 'stock_name': str(r[1] or '')} for r in cursor.fetchall() if r and r[0]]
    conn.close()

    v4_map = {x['stock_code']: x['stock_name'] for x in v4_items}
    v4_set = set(v4_map.keys())

    base_on_date = [r for r in base_rows if str(r.get('signal_date') or '') == target_date]
    v42_base_map = {}
    for r in base_on_date:
        code = str(r.get('stock_code') or '').strip()
        if not code:
            continue
        v42_base_map[code] = str(r.get('stock_name') or '').strip()
    v42_base_set = set(v42_base_map.keys())

    removed_set = {
        str(r.get('stock_code') or '').strip()
        for r in diff_rows
        if str(r.get('signal_date') or '') == target_date and str(r.get('change_type') or '') == 'removed_by_hardening'
    }
    v42_hardened_set = set([c for c in v42_base_set if c not in removed_set])

    inter_base = v4_set.intersection(v42_base_set)
    inter_hard = v4_set.intersection(v42_hardened_set)
    only_v4 = sorted(v4_set - v42_hardened_set)
    only_hard = sorted(v42_hardened_set - v4_set)

    rate_base = 0.0
    rate_hard = 0.0
    daily_diff_rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_base_hardened_daily_diff.csv')
    for r in daily_diff_rows:
        if str(r.get('signal_date') or '') == target_date:
            rate_base = _v4_lab_to_float(r.get('base_rate'), 0.0)
            rate_hard = _v4_lab_to_float(r.get('hard_rate'), 0.0)
            break

    def _sample(codes, name_map_a, name_map_b, n=12):
        out = []
        for code in list(codes)[:n]:
            out.append({'stock_code': code, 'stock_name': name_map_a.get(code) or name_map_b.get(code) or ''})
        return out

    warnings = []
    if v4_dates and v42_dates and v4_dates[-1] != v42_dates[-1]:
        warnings.append(f"Data freshness mismatch: V4 latest={v4_dates[-1]}, V4.2 latest={v42_dates[-1]}")
    if req_date and req_date != target_date:
        warnings.append(f"Requested date {req_date} fallback to {target_date}")

    return safe_jsonify(
        {
            'meta': {
                'target_date': target_date,
                'latest_v4_date': (v4_dates[-1] if v4_dates else None),
                'latest_v42_date': (v42_dates[-1] if v42_dates else None),
                'latest_common_date': (common_dates[-1] if common_dates else None),
                'candidate_dates': candidate_dates[-40:],
            },
            'counts': {
                'v4_count': len(v4_set),
                'v42_base_count': len(v42_base_set),
                'v42_hardened_count': len(v42_hardened_set),
                'overlap_base_count': len(inter_base),
                'overlap_hardened_count': len(inter_hard),
            },
            'ratios': {
                'hardened_vs_v4': (len(v42_hardened_set) / len(v4_set)) if len(v4_set) else 0.0,
                'hardened_vs_base': (len(v42_hardened_set) / len(v42_base_set)) if len(v42_base_set) else 0.0,
                'base_vs_v4': (len(v42_base_set) / len(v4_set)) if len(v4_set) else 0.0,
            },
            'quality': {
                'base_success_rate': rate_base,
                'hardened_success_rate': rate_hard,
                'delta_success_rate': rate_hard - rate_base,
            },
            'warnings': warnings,
            'samples': {
                'only_v4': _sample(only_v4, v4_map, v42_base_map),
                'only_v42_hardened': _sample(only_hard, v42_base_map, v4_map),
                'intersection_hardened': _sample(sorted(inter_hard), v4_map, v42_base_map),
            },
        }
    )


def _v4_lab_read_live_compare_history():
    p = V4_LAB_OUTPUT_DIR / 'v4_2_live_compare_history.csv'
    return _v4_lab_read_csv_rows(p)


def _v4_lab_upsert_live_compare_history(row):
    p = V4_LAB_OUTPUT_DIR / 'v4_2_live_compare_history.csv'
    fields = [
        'run_date',
        'market_state',
        'v4_count',
        'v42_base_count',
        'v42_hardened_count',
        'keep_rate_base',
        'keep_rate_hardened',
        'base_ready_n',
        'base_success_n',
        'base_success_rate',
        'hard_ready_n',
        'hard_success_n',
        'hard_success_rate',
        'delta_success_rate',
    ]
    rows = _v4_lab_read_csv_rows(p)
    by_date = {str(r.get('run_date') or ''): r for r in rows if str(r.get('run_date') or '')}
    by_date[str(row.get('run_date') or '')] = {k: row.get(k, '') for k in fields}
    merged = [by_date[k] for k in sorted(by_date.keys())]
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(merged)
    return merged


@app.route('/api/cup-handle-lab/v4-pool-compare', methods=['GET'])
def cup_handle_lab_v4_pool_compare():
    """
    Run V4.2 inside V4 pool on a specific V4 run date, then output:
    - V4 base set size
    - V4.2 base/hardened size
    - process transparency (matched/failed reasons)
    - success validation (T+8 strict) on ready samples
    """
    req_date = (request.args.get('date') or '').strip()
    limit = _safe_int_arg('limit', 200, min_value=50, max_value=800)
    persist = _safe_int_arg('persist', 1, min_value=0, max_value=1) == 1

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, run_date
        FROM screener_runs
        WHERE screener_name = ? AND status = 'completed'
        ORDER BY run_date DESC, id DESC
        LIMIT 120
        """,
        ('coffee_cup_v4',),
    )
    run_rows = cur.fetchall()
    if not run_rows:
        conn.close()
        return safe_jsonify({'error': 'no completed coffee_cup_v4 runs'}), 404
    date_to_run = {}
    for r in run_rows:
        rid = int(r[0])
        d = str(r[1] or '')
        if d and d not in date_to_run:
            date_to_run[d] = rid
    all_dates = sorted(date_to_run.keys())
    # Delivery date fallback:
    # If today's run date exists but market data not updated, fallback to previous effective trading date.
    stock_conn = get_stock_db_connection()
    try:
        stock_cur = stock_conn.cursor()
        stock_cur.execute("SELECT MAX(trade_date) AS max_trade_date FROM daily_prices")
        rmax = stock_cur.fetchone()
        max_trade_date = str((rmax['max_trade_date'] if isinstance(rmax, dict) else rmax[0]) or '')
    finally:
        stock_conn.close()

    fallback_applied = False
    if req_date:
        target_date = req_date
    else:
        # pick latest V4 completed run date that is <= latest trade_date, else fallback to latest run date
        candidates = [d for d in all_dates if (not max_trade_date or d <= max_trade_date)]
        if candidates:
            target_date = candidates[-1]
            fallback_applied = (target_date != all_dates[-1])
        else:
            target_date = all_dates[-1] if all_dates else ''
    run_id = date_to_run.get(target_date)
    if not run_id:
        conn.close()
        return safe_jsonify({'error': f'run date not found: {target_date}', 'candidate_dates': all_dates[-80:]}), 400

    cur.execute(
        """
        SELECT stock_code, stock_name, extra_data
        FROM screener_results
        WHERE run_id = ?
        """,
        (run_id,),
    )
    raw_items = cur.fetchall()
    conn.close()

    if not raw_items:
        return safe_jsonify({'error': f'no screener_results for run_date={target_date}'}), 404

    # Build V4 pool rows with typed features.
    base_rows = []
    for rr in raw_items:
        code = str(rr[0] or '').strip()
        if not code:
            continue
        name = str(rr[1] or '')
        extra_raw = rr[2]
        extra = {}
        if isinstance(extra_raw, str):
            try:
                extra = json.loads(extra_raw) if extra_raw else {}
            except Exception:
                extra = {}
        elif isinstance(extra_raw, dict):
            extra = extra_raw
        rim = _v4_lab_to_float(extra.get('rim_interval'), 0.0)
        cup = _v4_lab_to_float(extra.get('cup_depth'), 0.0)
        amount = _v4_lab_to_float(extra.get('amount_ratio'), 0.0)
        handle_len = _v4_lab_to_float(extra.get('handle_length'), 0.0)
        rim_band = 'narrow' if rim <= 70 else 'wide'
        cup_band = 'deep' if cup > 0.22 else 'shallow'
        segment = f'{rim_band}_{cup_band}'

        g_rhythm = 1 if rim <= 80 else 0
        g_shape = 1 if (0.15 < cup <= 0.30 or handle_len > 9) else 0
        g_flow = 1 if amount <= 2.13 else 0
        gate_count = g_rhythm + g_shape + g_flow
        enh = 0.0
        if g_rhythm:
            enh += 1.0 if cup > 0.12 else 0.0
        if g_shape:
            enh += 1.0 if amount <= 2.4 else 0.0
        if g_flow:
            enh += 1.0 if rim <= 75 else 0.0
        base_rows.append(
            {
                'stock_code': code,
                'stock_name': name,
                'rim_interval': rim,
                'cup_depth': cup,
                'amount_ratio': amount,
                'handle_length': handle_len,
                'segment_id': segment,
                'gate_count': gate_count,
                'enhancement_score': enh,
            }
        )

    # Determine market state for this run date.
    st = _v4_lab_compute_market_state(target_date)
    market_state = str(st.get('market_state') or 'S2_neutral')

    candidate_path = V4_LAB_OUTPUT_DIR / 'v4_2_dynamic_candidate_latest.json'
    hardened_path = V4_LAB_OUTPUT_DIR / 'v4_2_dynamic_hardened_candidate_latest.json'
    if not candidate_path.exists():
        return safe_jsonify({'error': 'candidate snapshot missing'}), 404
    try:
        candidate = json.loads(candidate_path.read_text(encoding='utf-8'))
    except Exception:
        candidate = {}
    try:
        hardened = json.loads(hardened_path.read_text(encoding='utf-8')) if hardened_path.exists() else {}
    except Exception:
        hardened = {}

    state_obj = (candidate.get('states') or {}).get(market_state) or {}
    routes = state_obj.get('routing_top3') or []
    if not routes:
        return safe_jsonify({'error': f'no routing_top3 for market_state={market_state}'}), 400
    primary = routes[0]
    primary_desc = str(primary.get('description') or '')
    primary_cluster = str(primary.get('cluster_id') or '')
    route_fn = _v4_lab_cluster_fn(primary_desc)

    # Hardening profile (optional)
    profile = (hardened.get('hardening') or {}).get('profile') or {}
    s1_floor = _v4_lab_to_float(profile.get('s1_score_floor'), 0.0)
    s3_floor = _v4_lab_to_float(profile.get('s3_score_floor'), 0.0)
    gate_floor_s1 = _v4_lab_to_int(profile.get('s1_gate_floor'), 0)
    gate_floor_s3 = _v4_lab_to_int(profile.get('s3_gate_floor'), 0)

    base_selected = []
    hard_selected = []
    process = {'route_miss': 0, 'hard_fail': 0, 'base_pass': 0, 'hard_pass': 0}
    for r in base_rows:
        rim = float(r['rim_interval'])
        amount = float(r['amount_ratio'])
        gate_count = int(r['gate_count'])
        enh = float(r['enhancement_score'])
        if market_state == 'S1_risk_on':
            align = 1.0 if rim <= 75 else 0.4
        elif market_state == 'S2_neutral':
            align = 1.0 if 58 < rim <= 91 else 0.6
        else:
            align = 1.0 if (amount <= 2.13 and float(r['cup_depth']) > 0.16) else 0.4
        stability_prior = 1.0 if rim <= 70 else (0.8 if rim <= 80 else 0.5)
        dynamic_score = round(0.40 * gate_count + 0.20 * enh + 0.25 * align + 0.15 * stability_prior, 6)
        rr = dict(r)
        rr.update({'market_state': market_state, 'cluster_id': primary_cluster, 'cluster_desc': primary_desc, 'dynamic_score': dynamic_score})

        if not route_fn(rr):
            process['route_miss'] += 1
            continue
        base_selected.append(rr)
        process['base_pass'] += 1

        hard_ok = True
        if market_state == 'S1_risk_on':
            hard_ok = dynamic_score >= s1_floor and gate_count >= gate_floor_s1
        elif market_state == 'S3_risk_off':
            hard_ok = dynamic_score >= s3_floor and gate_count >= gate_floor_s3
        if hard_ok:
            hard_selected.append(rr)
            process['hard_pass'] += 1
        else:
            process['hard_fail'] += 1

    base_code_set = {x['stock_code'] for x in base_selected}
    hard_code_set = {x['stock_code'] for x in hard_selected}

    # Success validation for T+8 strict on samples that already have 8 forward bars.
    spec = {'strength': 0.04, 'drawdown': 0.03, 'up_days_min': 5}
    base_ready = base_succ = 0
    hard_ready = hard_succ = 0
    for x in base_selected:
        ev = _v4_lab_eval_success_t8(x['stock_code'], target_date, spec['strength'], spec['drawdown'], spec['up_days_min'])
        if not ev.get('ready'):
            continue
        base_ready += 1
        base_succ += _v4_lab_to_int(ev.get('is_success_strict'), 0)
    for x in hard_selected:
        ev = _v4_lab_eval_success_t8(x['stock_code'], target_date, spec['strength'], spec['drawdown'], spec['up_days_min'])
        if not ev.get('ready'):
            continue
        hard_ready += 1
        hard_succ += _v4_lab_to_int(ev.get('is_success_strict'), 0)

    base_rate = (base_succ / base_ready) if base_ready else 0.0
    hard_rate = (hard_succ / hard_ready) if hard_ready else 0.0

    row = {
        'run_date': target_date,
        'market_state': market_state,
        'v4_count': len(base_rows),
        'v42_base_count': len(base_selected),
        'v42_hardened_count': len(hard_selected),
        'keep_rate_base': round((len(base_selected) / len(base_rows)) if base_rows else 0.0, 6),
        'keep_rate_hardened': round((len(hard_selected) / len(base_rows)) if base_rows else 0.0, 6),
        'base_ready_n': base_ready,
        'base_success_n': base_succ,
        'base_success_rate': round(base_rate, 6),
        'hard_ready_n': hard_ready,
        'hard_success_n': hard_succ,
        'hard_success_rate': round(hard_rate, 6),
        'delta_success_rate': round(hard_rate - base_rate, 6),
    }
    if persist:
        history_rows = _v4_lab_upsert_live_compare_history(row)
    else:
        history_rows = _v4_lab_read_live_compare_history()

    removed = [x for x in base_selected if x['stock_code'] not in hard_code_set]
    kept = hard_selected[:]
    base_sorted = base_selected[:]
    v4_sorted = base_rows[:]
    v4_sorted.sort(key=lambda x: (float(x.get('gate_count') or 0), float(x.get('enhancement_score') or 0.0)), reverse=True)
    base_sorted.sort(key=lambda x: float(x.get('dynamic_score') or 0.0), reverse=True)
    removed.sort(key=lambda x: (float(x.get('dynamic_score') or 0.0), int(x.get('gate_count') or 0)), reverse=True)
    kept.sort(key=lambda x: float(x.get('dynamic_score') or 0.0), reverse=True)

    warnings = []
    if base_ready == 0:
        warnings.append('当前日期尚无完整T+8可验证样本，成功率验证将随时间补全')

    # Enrich delivery pool rows with sector (板块) and replay-history stats for better UI inspection.
    hist_by_code = {}
    try:
        replay_rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_replay_daily_pool.csv')
        by_code_date = {}
        for r in replay_rows:
            d = str(r.get('signal_date') or '').strip()
            code = str(r.get('stock_code') or '').strip()
            if not d or not code:
                continue
            raw_s = r.get('is_success_strict')
            succ_val = None
            if raw_s is not None and str(raw_s).strip() != '':
                succ_val = 1 if _v4_lab_to_int(raw_s, 0) == 1 else 0
            key = (code, d)
            prev = by_code_date.get(key)
            if prev is None:
                by_code_date[key] = {'succ': succ_val}
            else:
                if succ_val == 1:
                    prev['succ'] = 1
                elif prev.get('succ') is None and succ_val == 0:
                    prev['succ'] = 0

        by_code = {}
        for (code, d), v in by_code_date.items():
            bucket = by_code.get(code)
            if not bucket:
                bucket = {'dates': set(), 'ready_n': 0, 'succ_n': 0}
                by_code[code] = bucket
            bucket['dates'].add(d)
            succ = v.get('succ')
            if succ in (0, 1):
                bucket['ready_n'] += 1
                if succ == 1:
                    bucket['succ_n'] += 1

        for code, bucket in by_code.items():
            ready_n = int(bucket.get('ready_n') or 0)
            succ_n = int(bucket.get('succ_n') or 0)
            hist_by_code[code] = {
                'history_cup_n': len(bucket.get('dates') or set()),
                'history_ready_n': ready_n,
                'history_success_n': succ_n,
                'history_success_rate': (succ_n / ready_n) if ready_n > 0 else None,
                'history_has_success': (succ_n > 0),
            }
    except Exception:
        hist_by_code = {}

    sector_map = {}
    try:
        code_list = []
        for bag in (v4_sorted[:limit], base_sorted[:limit], kept[:limit]):
            for x in bag:
                c0 = str(x.get('stock_code') or '').strip()
                if c0:
                    code_list.append(c0)
        code_list = sorted(set(code_list))
        stock_db_path = DASHBOARD_DIR.parent / 'data' / 'stock_data.db'
        if stock_db_path.exists() and code_list:
            conn_meta = sqlite3.connect(stock_db_path)
            conn_meta.row_factory = sqlite3.Row
            cur_meta = conn_meta.cursor()
            placeholders = ','.join(['?'] * len(code_list))
            cur_meta.execute(
                f"""
                SELECT code, COALESCE(sector_lv1,'') AS sector_lv1, COALESCE(sector_lv2,'') AS sector_lv2, COALESCE(industry,'') AS industry
                FROM stock_meta
                WHERE code IN ({placeholders})
                """,
                tuple(code_list),
            )
            for r in cur_meta.fetchall():
                sector_map[str(r['code'])] = {
                    'industry': str(r['industry'] or ''),
                    'sector_lv1': str(r['sector_lv1'] or ''),
                    'sector_lv2': str(r['sector_lv2'] or ''),
                }
            conn_meta.close()
    except Exception:
        sector_map = {}

    def _enrich_delivery_row(d: dict):
        code = str(d.get('stock_code') or '').strip()
        s = sector_map.get(code) or {}
        h = hist_by_code.get(code) or {}
        out = dict(d)
        out.update(
            {
                'industry': s.get('industry') or '',
                'sector_lv1': s.get('sector_lv1') or '',
                'sector_lv2': s.get('sector_lv2') or '',
                'history_cup_n': h.get('history_cup_n'),
                'history_success_n': h.get('history_success_n'),
                'history_success_rate': h.get('history_success_rate'),
                'history_has_success': h.get('history_has_success'),
            }
        )
        return out

    return safe_jsonify(
        {
            'meta': {
                'target_date': target_date,
                'requested_date': req_date or None,
                'latest_v4_run_date': all_dates[-1] if all_dates else None,
                'latest_trade_date': max_trade_date or None,
                'fallback_to_effective_trade_date': bool(fallback_applied),
                'candidate_dates': all_dates[-80:],
                'market_state': market_state,
                'route_cluster_id': primary_cluster,
                'route_desc': primary_desc,
                'lab_mode': 'v42_in_v4_pool_open_process',
            },
            'counts': {
                'v4_count': len(base_rows),
                'v42_base_count': len(base_selected),
                'v42_hardened_count': len(hard_selected),
            },
            'ratios': {
                'base_vs_v4': (len(base_selected) / len(base_rows)) if base_rows else 0.0,
                'hardened_vs_v4': (len(hard_selected) / len(base_rows)) if base_rows else 0.0,
                'hardened_vs_base': (len(hard_selected) / len(base_selected)) if base_selected else 0.0,
            },
            'quality': {
                'label_spec': spec,
                'base_ready_n': base_ready,
                'base_success_n': base_succ,
                'base_success_rate': base_rate,
                'hard_ready_n': hard_ready,
                'hard_success_n': hard_succ,
                'hard_success_rate': hard_rate,
                'delta_success_rate': hard_rate - base_rate,
            },
            'process': process,
            'samples': {
                'kept_top': [
                    {
                        'signal_date': target_date,
                        'stock_code': x.get('stock_code'),
                        'stock_name': x.get('stock_name'),
                        'segment_id': x.get('segment_id'),
                        'dynamic_score': x.get('dynamic_score'),
                        'gate_count': x.get('gate_count'),
                    }
                    for x in kept[:20]
                ],
                'removed_top': [
                    {
                        'signal_date': target_date,
                        'stock_code': x.get('stock_code'),
                        'stock_name': x.get('stock_name'),
                        'segment_id': x.get('segment_id'),
                        'dynamic_score': x.get('dynamic_score'),
                        'gate_count': x.get('gate_count'),
                    }
                    for x in removed[:20]
                ],
            },
            'delivery_pool': {
                'limit': limit,
                'v4_today': [
                    _enrich_delivery_row(
                        {
                        'signal_date': target_date,
                        'stock_code': x.get('stock_code'),
                        'stock_name': x.get('stock_name'),
                        'segment_id': x.get('segment_id'),
                        'gate_count': x.get('gate_count'),
                        'enhancement_score': x.get('enhancement_score'),
                        }
                    )
                    for x in v4_sorted[:limit]
                ],
                'v42_base_today': [
                    _enrich_delivery_row(
                        {
                        'signal_date': target_date,
                        'stock_code': x.get('stock_code'),
                        'stock_name': x.get('stock_name'),
                        'segment_id': x.get('segment_id'),
                        'dynamic_score': x.get('dynamic_score'),
                        'gate_count': x.get('gate_count'),
                        'route': x.get('cluster_id'),
                        }
                    )
                    for x in base_sorted[:limit]
                ],
                'v42_hardened_today': [
                    _enrich_delivery_row(
                        {
                        'signal_date': target_date,
                        'stock_code': x.get('stock_code'),
                        'stock_name': x.get('stock_name'),
                        'segment_id': x.get('segment_id'),
                        'dynamic_score': x.get('dynamic_score'),
                        'gate_count': x.get('gate_count'),
                        'route': x.get('cluster_id'),
                        }
                    )
                    for x in kept[:limit]
                ],
            },
            'history_tail': history_rows[-40:],
            'warnings': warnings,
        }
    )


@app.route('/api/cup-handle-lab/diff', methods=['GET'])
def cup_handle_lab_diff():
    limit = _safe_int_arg('limit', 60, min_value=10, max_value=400)
    rows = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_base_hardened_daily_diff.csv')
    rows.sort(key=lambda r: str(r.get('signal_date') or ''), reverse=True)
    page = rows[:limit]
    out = []
    for r in page:
        out.append(
            {
                'signal_date': r.get('signal_date'),
                'base_n': _v4_lab_to_int(r.get('base_n'), 0),
                'base_success': _v4_lab_to_int(r.get('base_success'), 0),
                'base_rate': _v4_lab_to_float(r.get('base_rate'), 0.0),
                'hard_n': _v4_lab_to_int(r.get('hard_n'), 0),
                'hard_success': _v4_lab_to_int(r.get('hard_success'), 0),
                'hard_rate': _v4_lab_to_float(r.get('hard_rate'), 0.0),
                'removed_n': _v4_lab_to_int(r.get('removed_n'), 0),
                'added_n': _v4_lab_to_int(r.get('added_n'), 0),
            }
        )
    return safe_jsonify({'items': out, 'total': len(rows), 'limit': limit})


@app.route('/api/cup-handle-lab/audit', methods=['GET'])
def cup_handle_lab_audit():
    table = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_hardened_audit_table.csv')
    examples = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_hardened_removed_examples.csv')
    alerts = _v4_lab_read_csv_rows(V4_LAB_OUTPUT_DIR / 'v4_2_phaseC_alerts.csv')

    return safe_jsonify(
        {
            'rules': table,
            'removed_examples': examples[:50],
            'alerts': alerts,
            'refresh_mode': {
                'default': 'manual',
                'hint': 'detect_new_snapshot_then_prompt_refresh',
            },
        }
    )



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
        readiness = _check_five_flags_unprocessed_data_readiness()

        cursor.execute('SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool')
        total_pools = cursor.fetchone()['cnt']

        unprocessed_pools = int(readiness.get('pending_pool_count') or 0)

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
            'readiness_reason': readiness.get('reason'),
            'latest_trade_date': readiness.get('latest_trade_date'),
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


def _summarize_five_flags_failure_reason(text: str) -> str:
    raw = (text or '').strip()
    if not raw:
        return '未知错误'
    lower = raw.lower()
    if 'module not found' in lower or 'modulenotfounderror' in lower or 'importerror' in lower:
        return '依赖或模块缺失'
    if 'timeout' in lower or 'timed out' in lower or 'network' in lower or 'connection' in lower or '502' in lower:
        return '网络或外部服务异常'
    if 'sqlite' in lower or 'database' in lower or 'db' in lower:
        return '数据库访问异常'
    if 'permission' in lower or 'denied' in lower:
        return '权限异常'
    if 'invalid a-share stock' in lower or 'not_in_stocks' in lower:
        return '股票池存在无效A股代码'
    return raw[:120]


@app.route('/api/five-flags/screening-logs', methods=['GET'])
def five_flags_screening_logs():
    """Readable screening logs for manual/auto runs."""
    try:
        limit = _safe_int_arg('limit', 20, min_value=1, max_value=100)
        _drain_five_flags_queue_once()
        queue_items = sorted(
            _refresh_five_flags_queue_status(),
            key=lambda x: x.get('requested_at') or '',
            reverse=True
        )
        queue_items = [
            x for x in queue_items
            if str(x.get('source') or '') in ('manual_run', 'daily_auto', 'pool_upload')
        ][:limit]

        runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
        run_by_id = {r.get('run_id'): r for r in runs}

        items = []
        for job in queue_items:
            run = run_by_id.get(job.get('run_id')) if job.get('run_id') else None
            run_summary = {}
            if run and run.get('log_file'):
                run_summary = _parse_five_flags_run_summary_from_log(run.get('log_file'))

            total_stocks = int(
                (run or {}).get('total_stocks')
                or run_summary.get('total_stocks')
                or 0
            )
            total_matches = int(
                (run or {}).get('total_matches')
                or run_summary.get('total_matches')
                or 0
            )
            failed_stocks = int(
                (run or {}).get('failed_stocks')
                or run_summary.get('failed_stocks')
                or 0
            )

            status = str(job.get('status') or 'unknown')
            reason = ''
            if status == 'failed':
                reason = _summarize_five_flags_failure_reason(
                    str(job.get('error') or (run or {}).get('error') or '')
                )
            elif status == 'completed':
                if total_stocks <= 0:
                    reason = '无待筛查股票'
                elif failed_stocks > 0:
                    reason = '部分股票筛查失败'
                else:
                    reason = '筛查完成'
            elif status == 'started':
                reason = '正在筛查中'
            elif status == 'queued':
                reason = '排队等待执行'

            items.append({
                'job_id': job.get('job_id'),
                'run_id': job.get('run_id'),
                'source': job.get('source'),
                'status': status,
                'requested_at': job.get('requested_at'),
                'started_at': job.get('started_at'),
                'completed_at': job.get('completed_at') or (run or {}).get('completed_at'),
                'target_trade_date': (run or {}).get('target_trade_date'),
                'total_stocks': total_stocks,
                'total_matches': total_matches,
                'failed_stocks': failed_stocks,
                'reason': reason,
            })

        latest_updated_at = next(
            (x.get('completed_at') or x.get('started_at') or x.get('requested_at') for x in items if x),
            None
        )
        return safe_jsonify({
            'updated_at': latest_updated_at,
            'items': items,
        })
    except Exception as e:
        return jsonify({'error': f'failed to build five-flags screening logs: {str(e)}'}), 500


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
    from pathlib import Path as _Path
    from werkzeug.utils import secure_filename as _secure_filename
    original_name = _Path(str(upload_file.filename)).name
    safe_name = _secure_filename(original_name) or f"pool_{uuid.uuid4().hex}"
    temp_path = os.path.join(temp_dir, safe_name)
    try:
        upload_file.save(temp_path)
        upload_result = handle_lao_ya_tou_pool_upload(
            temp_path,
            force_overwrite=force_overwrite,
            original_filename=original_name
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


def _assistant_percentiles(values, percentiles):
    seq = [float(x) for x in values if isinstance(x, (int, float)) and not math.isnan(float(x))]
    if not seq:
        return {str(p): None for p in percentiles}
    seq.sort()

    def pick(pct):
        if pct <= 0:
            return seq[0]
        if pct >= 100:
            return seq[-1]
        k = (len(seq) - 1) * (pct / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return seq[int(k)]
        d0 = seq[int(f)] * (c - k)
        d1 = seq[int(c)] * (k - f)
        return d0 + d1

    return {str(p): pick(p) for p in percentiles}


def _assistant_get_table_columns(conn, table_name: str):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    rows = cursor.fetchall()
    return {row['name'] for row in rows} if rows else set()


def _assistant_load_screener_class(screener_name: str):
    import re
    import importlib.util as _ilu

    workspace_root = DASHBOARD_DIR.parent
    possible_files = [
        workspace_root / f"{screener_name}.py",
        workspace_root / "screeners" / f"{screener_name}.py",
        workspace_root / f"{screener_name}_screener.py",
        workspace_root / "screeners" / f"{screener_name}_screener.py",
        workspace_root / "scripts" / f"{screener_name}.py",
        workspace_root / "scripts" / f"{screener_name}_screener.py",
    ]
    if screener_name == 'coffee_cup_v4':
        possible_files.extend([
            workspace_root / "screeners" / "coffee_cup_handle_screener_v4.py",
            workspace_root / "scripts" / "coffee_cup_handle_screener_v4.py",
        ])

    filepath = next((p for p in possible_files if p.exists()), None)
    if not filepath:
        raise FileNotFoundError(f"screener file not found: {screener_name}")

    try:
        content = filepath.read_text(encoding='utf-8')
        match = re.search(r'class\s+(\w+Screener(?:V?\d*)?)\s*[\(:]', content)
        if match:
            class_name = match.group(1)
        else:
            class_name = str(screener_name).title().replace('_', '')
    except Exception:
        class_name = str(screener_name).title().replace('_', '')

    module_key = f"assistant_screener_{screener_name}"
    spec = _ilu.spec_from_file_location(module_key, filepath)
    module = _ilu.module_from_spec(spec)
    sys.modules[module_key] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def _assistant_screener_param_overrides(screener_names):
    from config_loader import ConfigLoader

    conn = get_db_connection()
    cursor = conn.cursor()
    out = []
    for screener_name in screener_names:
        db_row = None
        try:
            cursor.execute(
                'SELECT display_name, category, current_version, updated_at FROM screener_configs WHERE screener_name = ?',
                (screener_name,)
            )
            db_row = cursor.fetchone()
        except Exception:
            db_row = None

        config = ConfigLoader.load_config(screener_name, prefer_database=True) or {}
        config_params = config.get('parameters') if isinstance(config, dict) else {}
        try:
            cls = _assistant_load_screener_class(screener_name)
            schema = cls.get_parameter_schema() if hasattr(cls, 'get_parameter_schema') else {}
        except Exception as exc:
            out.append({
                'screener': screener_name,
                'error': str(exc),
                'overrides': [],
                'schema_param_count': 0
            })
            continue

        overrides = []
        if isinstance(schema, dict):
            for param_name, param_schema in schema.items():
                default_value = param_schema.get('default') if isinstance(param_schema, dict) else None
                payload = config_params.get(param_name) if isinstance(config_params, dict) else None
                current_value = payload.get('value') if isinstance(payload, dict) else None
                if current_value is None:
                    continue
                if default_value is None:
                    continue
                if current_value != default_value:
                    overrides.append({
                        'param': param_name,
                        'default': default_value,
                        'current': current_value,
                        'display_name': payload.get('display_name') if isinstance(payload, dict) else None,
                        'description': payload.get('description') if isinstance(payload, dict) else None,
                        'group': payload.get('group') if isinstance(payload, dict) else None,
                        'type': payload.get('type') if isinstance(payload, dict) else None,
                    })

        out.append({
            'screener': screener_name,
            'display_name': (db_row['display_name'] if db_row and 'display_name' in db_row.keys() else config.get('display_name')),
            'category': (db_row['category'] if db_row and 'category' in db_row.keys() else config.get('category')),
            'version': (db_row['current_version'] if db_row and 'current_version' in db_row.keys() else config.get('metadata', {}).get('version')),
            'updated_at': (db_row['updated_at'] if db_row and 'updated_at' in db_row.keys() else None),
            'schema_param_count': len(schema) if isinstance(schema, dict) else 0,
            'override_count': len(overrides),
            'overrides': overrides,
        })
    conn.close()
    return out


@app.route('/api/assistant/lao-ya-tou/pool-commonalities', methods=['GET'])
def assistant_lao_ya_tou_pool_commonalities():
    try:
        processed = (request.args.get('processed') or 'all').lower()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        top_n = _safe_int_arg('top', 10, min_value=3, max_value=50)
        sample_size = _safe_int_arg('sample', 200, min_value=50, max_value=5000)

        where_parts = []
        params = []
        if processed in ('0', '1'):
            where_parts.append('processed = ?')
            params.append(int(processed))
        elif processed != 'all':
            return jsonify({'error': 'Invalid processed value. Use 0, 1, or all.'}), 400

        if start_date:
            where_parts.append('end_date >= ?')
            params.append(start_date)
        if end_date:
            where_parts.append('start_date <= ?')
            params.append(end_date)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

        conn = get_stock_db_connection()
        cursor = conn.cursor()

        cursor.execute(f'SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool {where_sql}', params)
        total_rows = int(cursor.fetchone()['cnt'])
        cursor.execute(f'SELECT COUNT(DISTINCT stock_code) AS cnt FROM lao_ya_tou_pool {where_sql}', params)
        unique_stocks = int(cursor.fetchone()['cnt'])
        cursor.execute(f'SELECT SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) AS cnt FROM lao_ya_tou_pool {where_sql}', params)
        processed_rows = int(cursor.fetchone()['cnt'] or 0)

        cursor.execute(f'''
            SELECT MIN(start_date) AS min_start_date,
                   MAX(end_date) AS max_end_date,
                   AVG(julianday(end_date) - julianday(start_date)) AS avg_window_days
            FROM lao_ya_tou_pool
            {where_sql}
        ''', params)
        _range_row = cursor.fetchone()
        range_row = dict(_range_row) if _range_row else {}

        cursor.execute(f'''
            SELECT file_name, COUNT(*) AS cnt
            FROM lao_ya_tou_pool
            {where_sql}
            GROUP BY file_name
            ORDER BY cnt DESC
            LIMIT ?
        ''', [*params, top_n])
        top_files = [{'file_name': r['file_name'], 'count': int(r['cnt'])} for r in cursor.fetchall()]

        sector_breakdown = []
        if 'stock_meta' in {r['name'] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
            where_parts_p = []
            if processed in ('0', '1'):
                where_parts_p.append('p.processed = ?')
            if start_date:
                where_parts_p.append('p.end_date >= ?')
            if end_date:
                where_parts_p.append('p.start_date <= ?')
            where_sql_p = f"WHERE {' AND '.join(where_parts_p)}" if where_parts_p else ''

            cursor.execute(f'''
                SELECT
                    COALESCE(NULLIF(TRIM(m.sector_lv1), ''), '未知') AS sector_lv1,
                    COUNT(DISTINCT p.stock_code) AS stock_count
                FROM lao_ya_tou_pool p
                LEFT JOIN stock_meta m ON m.code = p.stock_code
                {where_sql_p}
                GROUP BY COALESCE(NULLIF(TRIM(m.sector_lv1), ''), '未知')
                ORDER BY stock_count DESC
                LIMIT ?
            ''', [*params, top_n])
            sector_breakdown = [{'sector_lv1': r['sector_lv1'], 'stock_count': int(r['stock_count'])} for r in cursor.fetchall()]

        cursor.execute(f'''
            SELECT stock_code,
                   MIN(start_date) AS start_date,
                   MAX(end_date) AS end_date
            FROM lao_ya_tou_pool
            {where_sql}
            GROUP BY stock_code
            LIMIT ?
        ''', [*params, sample_size])
        sample_rows = cursor.fetchall()

        returns = []
        stmt_first = "SELECT close FROM daily_prices WHERE code = ? AND trade_date >= ? ORDER BY trade_date ASC LIMIT 1"
        stmt_last = "SELECT close FROM daily_prices WHERE code = ? AND trade_date <= ? ORDER BY trade_date DESC LIMIT 1"
        for r in sample_rows:
            code = r['stock_code']
            s = r['start_date']
            e = r['end_date']
            first_row = cursor.execute(stmt_first, (code, s)).fetchone()
            last_row = cursor.execute(stmt_last, (code, e)).fetchone()
            if not first_row or not last_row:
                continue
            first_close = first_row['close']
            last_close = last_row['close']
            try:
                first_close = float(first_close)
                last_close = float(last_close)
            except Exception:
                continue
            if first_close <= 0:
                continue
            returns.append((last_close / first_close - 1.0) * 100.0)

        p = _assistant_percentiles(returns, [0, 25, 50, 75, 100])
        perf_summary = {
            'sample_stocks': len(sample_rows),
            'sample_with_prices': len(returns),
            'return_pct': {
                'mean': (sum(returns) / len(returns)) if returns else None,
                'p0': p['0'],
                'p25': p['25'],
                'p50': p['50'],
                'p75': p['75'],
                'p100': p['100'],
            }
        }

        conn.close()

        return safe_jsonify({
            'filters': {
                'processed': processed,
                'start_date': start_date,
                'end_date': end_date,
                'top': top_n,
                'sample': sample_size,
            },
            'pool': {
                'rows': total_rows,
                'unique_stocks': unique_stocks,
                'processed_rows': processed_rows,
                'unprocessed_rows': total_rows - processed_rows,
                'min_start_date': range_row.get('min_start_date'),
                'max_end_date': range_row.get('max_end_date'),
                'avg_window_days': float(range_row.get('avg_window_days')) if range_row.get('avg_window_days') is not None else None,
            },
            'top_files': top_files,
            'sector_lv1_top': sector_breakdown,
            'price_performance': perf_summary
        })
    except Exception as e:
        return jsonify({'error': f'failed to analyze lao-ya-tou pool: {str(e)}'}), 500


@app.route('/api/assistant/lao-ya-tou/label-summary', methods=['GET'])
def assistant_lao_ya_tou_label_summary():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        top_n = _safe_int_arg('top', 30, min_value=1, max_value=365)

        where_parts = []
        params = []
        if start_date:
            where_parts.append('end_date >= ?')
            params.append(start_date)
        if end_date:
            where_parts.append('end_date <= ?')
            params.append(end_date)
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

        conn = get_stock_db_connection()
        cursor = conn.cursor()

        cursor.execute(f'SELECT COUNT(*) AS cnt FROM lao_ya_tou_pool {where_sql}', params)
        total_rows = int(cursor.fetchone()['cnt'])
        cursor.execute(f'SELECT COUNT(DISTINCT stock_code) AS cnt FROM lao_ya_tou_pool {where_sql}', params)
        unique_stocks = int(cursor.fetchone()['cnt'])
        cursor.execute(f'SELECT COUNT(DISTINCT end_date) AS cnt FROM lao_ya_tou_pool {where_sql}', params)
        unique_label_dates = int(cursor.fetchone()['cnt'])

        cursor.execute(f'''
            SELECT end_date AS label_date,
                   COUNT(*) AS rows,
                   COUNT(DISTINCT stock_code) AS stocks
            FROM lao_ya_tou_pool
            {where_sql}
            GROUP BY end_date
            ORDER BY end_date DESC
            LIMIT ?
        ''', [*params, top_n])
        by_date = [
            {'label_date': r['label_date'], 'rows': int(r['rows']), 'stocks': int(r['stocks'])}
            for r in cursor.fetchall()
        ]

        cursor.execute(f'''
            SELECT MIN(end_date) AS min_label_date,
                   MAX(end_date) AS max_label_date
            FROM lao_ya_tou_pool
            {where_sql}
        ''', params)
        _range_row = cursor.fetchone()
        range_row = dict(_range_row) if _range_row else {}

        conn.close()

        return safe_jsonify({
            'filters': {
                'start_date': start_date,
                'end_date': end_date,
                'top': top_n,
            },
            'labels': {
                'rows': total_rows,
                'unique_stocks': unique_stocks,
                'unique_label_dates': unique_label_dates,
                'min_label_date': range_row.get('min_label_date'),
                'max_label_date': range_row.get('max_label_date'),
            },
            'by_label_date': by_date,
        })
    except Exception as e:
        return jsonify({'error': f'failed to build lao-ya-tou label summary: {str(e)}'}), 500


@app.route('/api/assistant/lao-ya-tou/baseline-eval', methods=['GET'])
def assistant_lao_ya_tou_baseline_eval():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        max_dates = _safe_int_arg('max_dates', 5, min_value=1, max_value=60)
        max_stocks_per_date = _safe_int_arg('max_stocks_per_date', 50, min_value=1, max_value=500)

        import sys
        from pathlib import Path

        workspace_root = Path(__file__).resolve().parent.parent
        screeners_dir = workspace_root / 'screeners'
        if str(workspace_root) not in sys.path:
            sys.path.insert(0, str(workspace_root))
        if str(screeners_dir) not in sys.path:
            sys.path.insert(0, str(screeners_dir))

        from lao_ya_tou_zhou_xian_screener import LaoYaTouZhouXianParams
        from signal_detectors.base_lao_ya_tou_detector import BaseLaoYaTouDetector
        from signal_detectors.signal_classifier import SignalClassifier

        p = LaoYaTouZhouXianParams
        detector = BaseLaoYaTouDetector(
            ma5_period=p.MA5_PERIOD,
            ma10_period=p.MA10_PERIOD,
            ma30_period=p.MA30_PERIOD,
            local_high_window=p.LOCAL_HIGH_WINDOW,
            volume_contraction_threshold=p.VOLUME_CONTRACTION_THRESHOLD,
            min_gap=p.MIN_GAP,
            max_gap=p.MAX_GAP,
            min_days=p.MIN_DAYS,
            amplitude_lookback_days=p.AMPLITUDE_LOOKBACK_DAYS,
            amplitude_min_threshold=p.AMPLITUDE_MIN_THRESHOLD,
        )
        classifier = SignalClassifier(
            ma5_period=p.MA5_PERIOD,
            ma10_period=p.MA10_PERIOD,
            ma30_period=p.MA30_PERIOD,
            local_high_window=p.LOCAL_HIGH_WINDOW,
            volume_contraction_threshold=p.VOLUME_CONTRACTION_THRESHOLD,
            min_gap=p.MIN_GAP,
            max_gap=p.MAX_GAP,
            signal_1_min_gap=p.SIGNAL_1_MIN_GAP,
            signal_1_volume_ratio_min=p.SIGNAL_1_VOLUME_RATIO_MIN,
            signal_2_confirm_days=p.SIGNAL_2_CONFIRM_DAYS,
            signal_2_min_confirm_days=p.SIGNAL_2_MIN_CONFIRM_DAYS,
            signal_2_cross_lookback_days=p.SIGNAL_2_CROSS_LOOKBACK_DAYS,
            signal_3_breakout_lookback=p.SIGNAL_3_BREAKOUT_LOOKBACK,
        )

        where_parts = []
        params = []
        if start_date:
            where_parts.append('end_date >= ?')
            params.append(start_date)
        if end_date:
            where_parts.append('end_date <= ?')
            params.append(end_date)
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

        conn = get_stock_db_connection()
        cursor = conn.cursor()

        cursor.execute(f'''
            SELECT DISTINCT end_date AS label_date
            FROM lao_ya_tou_pool
            {where_sql}
            ORDER BY end_date DESC
            LIMIT ?
        ''', [*params, max_dates])
        label_dates = [r['label_date'] for r in cursor.fetchall()]

        total_samples = 0
        stage1_hits = 0
        stage2_hits = 0
        data_missing = 0
        errors = 0
        by_signal = {'signal_1': 0, 'signal_2': 0, 'signal_3': 0}
        by_date = []

        for label_date in label_dates:
            cursor.execute('''
                SELECT stock_code, stock_name
                FROM lao_ya_tou_pool
                WHERE end_date = ?
                LIMIT ?
            ''', (label_date, max_stocks_per_date))
            rows = cursor.fetchall()

            d_total = 0
            d_stage1 = 0
            d_stage2 = 0
            d_missing = 0
            d_errors = 0
            d_by_signal = {'signal_1': 0, 'signal_2': 0, 'signal_3': 0}

            for r in rows:
                code = r['stock_code']
                name = r['stock_name']
                d_total += 1
                try:
                    hit, df = detector.screen(code, name, label_date)
                    if df is None:
                        d_missing += 1
                        continue
                    if hit:
                        d_stage1 += 1
                        s = classifier.classify(df)
                        if s and isinstance(s, dict) and s.get('signal_type') in d_by_signal:
                            d_stage2 += 1
                            d_by_signal[str(s.get('signal_type'))] += 1
                except Exception:
                    d_errors += 1

            by_date.append({
                'label_date': label_date,
                'samples': d_total,
                'stage1_hits': d_stage1,
                'stage2_hits': d_stage2,
                'data_missing': d_missing,
                'errors': d_errors,
                'by_signal': d_by_signal,
            })

            total_samples += d_total
            stage1_hits += d_stage1
            stage2_hits += d_stage2
            data_missing += d_missing
            errors += d_errors
            for k in by_signal:
                by_signal[k] += int(d_by_signal.get(k) or 0)

        conn.close()

        stage1_recall = (stage1_hits / total_samples) if total_samples else None
        stage2_recall = (stage2_hits / total_samples) if total_samples else None

        return safe_jsonify({
            'filters': {
                'start_date': start_date,
                'end_date': end_date,
                'max_dates': max_dates,
                'max_stocks_per_date': max_stocks_per_date,
            },
            'params': {
                'MA5_PERIOD': p.MA5_PERIOD,
                'MA10_PERIOD': p.MA10_PERIOD,
                'MA30_PERIOD': p.MA30_PERIOD,
                'LOCAL_HIGH_WINDOW': p.LOCAL_HIGH_WINDOW,
                'VOLUME_CONTRACTION_THRESHOLD': p.VOLUME_CONTRACTION_THRESHOLD,
                'MIN_GAP': p.MIN_GAP,
                'MAX_GAP': p.MAX_GAP,
                'MIN_DAYS': p.MIN_DAYS,
                'AMPLITUDE_LOOKBACK_DAYS': p.AMPLITUDE_LOOKBACK_DAYS,
                'AMPLITUDE_MIN_THRESHOLD': p.AMPLITUDE_MIN_THRESHOLD,
                'SIGNAL_1_MIN_GAP': p.SIGNAL_1_MIN_GAP,
                'SIGNAL_1_VOLUME_RATIO_MIN': p.SIGNAL_1_VOLUME_RATIO_MIN,
                'SIGNAL_2_CONFIRM_DAYS': p.SIGNAL_2_CONFIRM_DAYS,
                'SIGNAL_2_MIN_CONFIRM_DAYS': p.SIGNAL_2_MIN_CONFIRM_DAYS,
                'SIGNAL_2_CROSS_LOOKBACK_DAYS': p.SIGNAL_2_CROSS_LOOKBACK_DAYS,
                'SIGNAL_3_BREAKOUT_LOOKBACK': p.SIGNAL_3_BREAKOUT_LOOKBACK,
            },
            'baseline': {
                'label_dates': label_dates,
                'samples': total_samples,
                'stage1_hits': stage1_hits,
                'stage2_hits': stage2_hits,
                'stage1_recall': stage1_recall,
                'stage2_recall': stage2_recall,
                'data_missing': data_missing,
                'errors': errors,
                'by_signal': by_signal,
            },
            'by_label_date': by_date,
        })
    except Exception as e:
        return jsonify({'error': f'failed to run lao-ya-tou baseline eval: {str(e)}'}), 500


@app.route('/api/assistant/lao-ya-tou/daily-compare', methods=['GET'])
def assistant_lao_ya_tou_daily_compare():
    try:
        req_date = request.args.get('date') or date.today().isoformat()
        auto_run = _parse_bool_arg('auto_run', True)
        include_codes = _parse_bool_arg('include_codes', True)
        max_codes = _safe_int_arg('max_codes', 300, min_value=0, max_value=5000)
        max_stocks = _safe_int_arg('max_stocks', 2000, min_value=100, max_value=6000)

        try:
            datetime.strptime(req_date, '%Y-%m-%d')
        except ValueError:
            return safe_jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

        is_td, effective = _resolve_effective_trade_date(req_date)
        non_trading_day = (not is_td)
        trade_date = effective

        ours_set: set[str] = set()
        ours_by_signal = {'signal_1': 0, 'signal_2': 0, 'signal_3': 0}
        ours_meta = {
            'computed': False,
            'processed_stocks': 0,
            'errors': 0,
            'max_stocks': max_stocks,
        }

        if auto_run:
            import sys as _sys
            from pathlib import Path as _Path

            workspace_root = _Path(__file__).resolve().parent.parent
            screeners_dir = workspace_root / 'screeners'
            if str(workspace_root) not in _sys.path:
                _sys.path.insert(0, str(workspace_root))
            if str(screeners_dir) not in _sys.path:
                _sys.path.insert(0, str(screeners_dir))

            from lao_ya_tou_zhou_xian_screener import LaoYaTouZhouXianParams
            from signal_detectors.base_lao_ya_tou_detector import BaseLaoYaTouDetector
            from signal_detectors.signal_classifier import SignalClassifier

            p = LaoYaTouZhouXianParams
            detector = BaseLaoYaTouDetector(
                ma5_period=p.MA5_PERIOD,
                ma10_period=p.MA10_PERIOD,
                ma30_period=p.MA30_PERIOD,
                local_high_window=p.LOCAL_HIGH_WINDOW,
                volume_contraction_threshold=p.VOLUME_CONTRACTION_THRESHOLD,
                min_gap=p.MIN_GAP,
                max_gap=p.MAX_GAP,
                min_days=p.MIN_DAYS,
                amplitude_lookback_days=p.AMPLITUDE_LOOKBACK_DAYS,
                amplitude_min_threshold=p.AMPLITUDE_MIN_THRESHOLD,
            )
            classifier = SignalClassifier(
                ma5_period=p.MA5_PERIOD,
                ma10_period=p.MA10_PERIOD,
                ma30_period=p.MA30_PERIOD,
                local_high_window=p.LOCAL_HIGH_WINDOW,
                volume_contraction_threshold=p.VOLUME_CONTRACTION_THRESHOLD,
                min_gap=p.MIN_GAP,
                max_gap=p.MAX_GAP,
                signal_1_min_gap=p.SIGNAL_1_MIN_GAP,
                signal_1_volume_ratio_min=p.SIGNAL_1_VOLUME_RATIO_MIN,
                signal_2_confirm_days=p.SIGNAL_2_CONFIRM_DAYS,
                signal_2_min_confirm_days=p.SIGNAL_2_MIN_CONFIRM_DAYS,
                signal_2_cross_lookback_days=p.SIGNAL_2_CROSS_LOOKBACK_DAYS,
                signal_3_breakout_lookback=p.SIGNAL_3_BREAKOUT_LOOKBACK,
            )

            conn = get_stock_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT code, name
                FROM stocks
                WHERE code IS NOT NULL
                ORDER BY code ASC
                '''
            )
            stock_rows = cursor.fetchall()
            conn.close()

            processed = 0
            errors = 0
            for row in stock_rows[:max_stocks]:
                code = str(row['code'] or '').strip()
                if not code:
                    continue
                name = str(row['name'] or '').strip()
                try:
                    ok, df = detector.screen(code, name, trade_date)
                    if (not ok) or df is None:
                        processed += 1
                        continue
                    sig = classifier.classify(df)
                    if not sig:
                        processed += 1
                        continue
                    st = str(sig.get('signal_type') or '').strip()
                    if st in ('signal_1', 'signal_2', 'signal_3'):
                        ours_set.add(code)
                        ours_by_signal[st] += 1
                    processed += 1
                except Exception:
                    errors += 1
                    processed += 1

            ours_meta = {
                'computed': True,
                'processed_stocks': processed,
                'errors': errors,
                'max_stocks': max_stocks,
            }

        conn = get_stock_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT stock_code, stock_name, file_name
            FROM lao_ya_tou_pool
            WHERE end_date = ?
            ''',
            (trade_date,)
        )
        tdx_rows = cursor.fetchall()
        conn.close()

        tdx_codes = [str(r['stock_code']).strip() for r in tdx_rows if r and r.get('stock_code')]
        tdx_set = set(tdx_codes)
        tdx_files = {}
        for r in tdx_rows:
            fn = str(r.get('file_name') or '').strip() or 'unknown'
            tdx_files[fn] = int(tdx_files.get(fn) or 0) + 1

        inter = sorted(ours_set & tdx_set)
        ours_only = sorted(ours_set - tdx_set)
        tdx_only = sorted(tdx_set - ours_set)

        intersection_count = len(inter)
        ours_count = len(ours_set)
        tdx_count = len(tdx_set)

        precision = (intersection_count / ours_count) if ours_count else None
        recall = (intersection_count / tdx_count) if tdx_count else None
        jaccard = (intersection_count / (ours_count + tdx_count - intersection_count)) if (ours_count + tdx_count - intersection_count) else None

        def _maybe_trim(xs: list[str]) -> list[str]:
            if max_codes <= 0:
                return []
            return xs[:max_codes]

        payload = {
            'requested_date': req_date,
            'trade_date': trade_date,
            'non_trading_day': non_trading_day,
            'our_screener': {
                'computed': bool(ours_meta.get('computed')),
                'processed_stocks': int(ours_meta.get('processed_stocks') or 0),
                'errors': int(ours_meta.get('errors') or 0),
                'max_stocks': int(ours_meta.get('max_stocks') or 0),
                'count': ours_count,
                'by_signal': ours_by_signal,
            },
            'tdx_upload': {
                'count': tdx_count,
                'by_file': [{'file_name': k, 'count': int(v)} for k, v in sorted(tdx_files.items(), key=lambda x: (-x[1], x[0]))],
            },
            'compare': {
                'intersection_count': intersection_count,
                'ours_only_count': len(ours_only),
                'tdx_only_count': len(tdx_only),
                'precision': precision,
                'recall': recall,
                'jaccard': jaccard,
            }
        }

        if include_codes:
            payload['codes'] = {
                'intersection': _maybe_trim(inter),
                'ours_only': _maybe_trim(ours_only),
                'tdx_only': _maybe_trim(tdx_only),
            }

        return safe_jsonify(payload)
    except Exception as e:
        return jsonify({'error': f'failed to compare lao-ya-tou daily results: {str(e)}'}), 500


@app.route('/api/assistant/five-flags/parameter-overrides', methods=['GET'])
def assistant_five_flags_parameter_overrides():
    try:
        screeners = [
            'er_ban_hui_tiao',
            'jin_feng_huang',
            'yin_feng_huang',
            'shi_pan_xian',
            'zhang_ting_bei_liang_yin',
        ]
        overrides = _assistant_screener_param_overrides(screeners)

        profile_file = DASHBOARD_DIR.parent / 'config' / 'screeners' / 'market_phase_profiles.json'
        phase_profiles = None
        if profile_file.exists():
            try:
                phase_profiles = json.loads(profile_file.read_text(encoding='utf-8'))
            except Exception:
                phase_profiles = None

        return safe_jsonify({
            'screeners': overrides,
            'phase_profiles': phase_profiles
        })
    except Exception as e:
        return jsonify({'error': f'failed to analyze screener parameters: {str(e)}'}), 500


@app.route('/api/assistant/query', methods=['POST'])
def assistant_query():
    try:
        payload = request.get_json(silent=True) or {}
        message = str(payload.get('message') or '').strip()
        if not message:
            return jsonify({'error': 'message is required'}), 400

        need_pool = any(k in message for k in ['股票池', '共同点', '老鸭头池', '池子'])
        need_params = any(k in message for k in ['参数', '阈值', '配置', '默认', '调整'])
        actions = []
        data = {}

        if need_pool:
            actions.append({'tool': 'lao_ya_tou_pool_commonalities'})
            resp = assistant_lao_ya_tou_pool_commonalities()
            resp_obj = resp[0] if isinstance(resp, tuple) else resp
            data['pool_commonalities'] = json.loads(resp_obj.get_data(as_text=True) or '{}')

        if need_params:
            actions.append({'tool': 'five_flags_parameter_overrides'})
            resp = assistant_five_flags_parameter_overrides()
            resp_obj = resp[0] if isinstance(resp, tuple) else resp
            data['parameter_overrides'] = json.loads(resp_obj.get_data(as_text=True) or '{}')

        if not actions:
            actions = [
                {'tool': 'lao_ya_tou_pool_commonalities', 'hint': '分析老鸭头股票池共同点'},
                {'tool': 'five_flags_parameter_overrides', 'hint': '查看五旗筛选器参数与默认值差异'},
            ]

        answer_parts = []
        if need_pool:
            answer_parts.append('已生成：老鸭头股票池共同点（统计口径 + 样本表现摘要）。')
        if need_params:
            answer_parts.append('已生成：五旗筛选器参数与默认值差异（可用于追溯“哪些参数被调过”）。')
        if not answer_parts:
            answer_parts.append('支持的问题：老鸭头池共同点、五旗筛选器参数差异。')

        return safe_jsonify({
            'message': message,
            'answer': '\n'.join(answer_parts),
            'actions': actions,
            'data': data
        })
    except Exception as e:
        return jsonify({'error': f'assistant query failed: {str(e)}'}), 500


def _assistant_rules_parse_codes(raw_codes):
    if raw_codes is None:
        return []
    if isinstance(raw_codes, list):
        parts = raw_codes
    else:
        parts = str(raw_codes).replace('\n', ',').replace(' ', ',').split(',')
    out = []
    for p in parts:
        c = str(p).strip()
        if not c:
            continue
        if len(c) == 6 and c.isdigit():
            out.append(c)
        else:
            return None
    seen = set()
    uniq = []
    for c in out:
        if c in seen:
            continue
        uniq.append(c)
        seen.add(c)
    return uniq


def _assistant_rules_get_trade_date(cursor, requested_date=None):
    if requested_date:
        row = cursor.execute(
            "SELECT MAX(trade_date) AS d FROM daily_prices WHERE trade_date <= ?",
            (requested_date,),
        ).fetchone()
        return row['d'] if row and row['d'] else None
    row = cursor.execute("SELECT MAX(trade_date) AS d FROM daily_prices").fetchone()
    return row['d'] if row and row['d'] else None


def _assistant_rules_sma(values, window):
    if window <= 0:
        return None
    if len(values) < window:
        return None
    return sum(values[-window:]) / float(window)


def _assistant_rules_ema(values, span):
    if span <= 0 or not values:
        return []
    alpha = 2.0 / (span + 1.0)
    out = []
    ema = float(values[0])
    out.append(ema)
    for v in values[1:]:
        ema = alpha * float(v) + (1.0 - alpha) * ema
        out.append(ema)
    return out


def _assistant_rules_rsi(values, period=14):
    if period <= 0 or len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(len(values) - period, len(values)):
        chg = float(values[i]) - float(values[i - 1])
        if chg >= 0:
            gains += chg
        else:
            losses += -chg
    avg_gain = gains / float(period)
    avg_loss = losses / float(period)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _assistant_rules_atr(highs, lows, closes, period=14):
    if period <= 0 or len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        h = float(highs[i])
        l = float(lows[i])
        pc = float(closes[i - 1])
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / float(period)


def _assistant_rules_weekly_bars(daily_rows):
    buckets = {}
    order = []
    for r in daily_rows:
        try:
            dt = datetime.strptime(r['trade_date'], '%Y-%m-%d').date()
        except Exception:
            continue
        iso = dt.isocalendar()
        key = (iso[0], iso[1])
        if key not in buckets:
            buckets[key] = {
                'trade_week': f"{iso[0]}-W{iso[1]:02d}",
                'open': float(r['open']),
                'high': float(r['high']),
                'low': float(r['low']),
                'close': float(r['close']),
                'volume': float(r.get('volume') or 0),
            }
            order.append(key)
        else:
            b = buckets[key]
            b['high'] = max(b['high'], float(r['high']))
            b['low'] = min(b['low'], float(r['low']))
            b['close'] = float(r['close'])
            b['volume'] += float(r.get('volume') or 0)
    return [buckets[k] for k in order]


def _assistant_rules_macd(values, fast=12, slow=26, signal=9):
    if not values:
        return None
    ema_fast = _assistant_rules_ema(values, fast)
    ema_slow = _assistant_rules_ema(values, slow)
    if len(ema_fast) != len(ema_slow):
        return None
    macd_line = [a - b for a, b in zip(ema_fast, ema_slow)]
    signal_line = _assistant_rules_ema(macd_line, signal)
    hist = [m - s for m, s in zip(macd_line, signal_line)]
    return {
        'macd': macd_line,
        'signal': signal_line,
        'hist': hist,
    }


def _assistant_rules_format_explanation(model_block):
    lines = []
    lines.append(f"模型：{model_block.get('model_name')}（{model_block.get('model_id')}）")
    lines.append(f"结论：{model_block.get('conclusion')}")
    for step in model_block.get('why_steps') or []:
        src = step.get('source') or {}
        src_txt = src.get('ref') or src.get('title') or '—'
        lines.append(f"依据【{src_txt}】的条件：{step.get('condition')} → 结论：{step.get('result')}")
    return '\n'.join(lines)


@app.route('/api/assistant/rules/analyze', methods=['GET'])
def assistant_rules_analyze():
    try:
        raw_codes = request.args.get('codes') or request.args.get('code')
        horizon = (request.args.get('horizon') or 'short').strip().lower()
        requested_date = (request.args.get('date') or '').strip() or None
        raw_models = (request.args.get('models') or '').strip()

        if horizon not in ('short', 'medium', 'long'):
            return jsonify({'error': 'horizon must be one of: short, medium, long'}), 400

        enabled_models = None
        if raw_models:
            parts = [p.strip().lower() for p in raw_models.replace(' ', ',').split(',') if p.strip()]
            normalized = []
            for p in parts:
                if p in ('elder', 'triple', 'triple_screen', 'triple-screen', 'ts'):
                    normalized.append('triple_screen')
                elif p in ('turtle', 'turtle_trading', 'turtle-trading'):
                    normalized.append('turtle')
                else:
                    return jsonify({'error': f'unknown model: {p}'}), 400
            enabled_models = sorted(set(normalized))
            if not enabled_models:
                return jsonify({'error': 'models is empty'}), 400

        codes = _assistant_rules_parse_codes(raw_codes)
        if codes is None:
            return jsonify({'error': 'codes must be 6-digit numbers, separated by comma'}), 400
        if not codes:
            return jsonify({'error': 'codes is required'}), 400
        if len(codes) > 20:
            return jsonify({'error': 'max 20 codes per request'}), 400

        conn = get_stock_db_connection()
        cursor = conn.cursor()

        trade_date = _assistant_rules_get_trade_date(cursor, requested_date=requested_date)
        if not trade_date:
            conn.close()
            return jsonify({'error': 'no trade_date found in daily_prices'}), 500

        SOURCES = {
            'elder_ts_trend': {'ref': 'RULEBOOK:ELDER_TRIPLE_SCREEN#TS1', 'title': '三重滤网：长周期趋势过滤'},
            'elder_ts_timing': {'ref': 'RULEBOOK:ELDER_TRIPLE_SCREEN#TS2', 'title': '三重滤网：中周期择时'},
            'elder_ts_entry': {'ref': 'RULEBOOK:ELDER_TRIPLE_SCREEN#TS3', 'title': '三重滤网：短周期入场触发'},
            'turtle_entry': {'ref': 'RULEBOOK:TURTLE#T1', 'title': '海龟交易：突破入场'},
            'turtle_exit': {'ref': 'RULEBOOK:TURTLE#T2', 'title': '海龟交易：通道退出'},
            'fund_quality': {'ref': 'RULEBOOK:FUNDAMENTAL#F1', 'title': '基本面：盈利质量与杠杆约束'},
            'model_select': {'ref': 'RULEBOOK:MODEL_ROUTER#R1', 'title': '模型路由：适用性过滤 + 打分排序'},
        }

        results = []
        for code in codes:
            stock_row = cursor.execute(
                "SELECT code,name,industry,area,list_date,total_market_cap,circulating_market_cap,pb_ratio,sector_lv1,sector_lv2,pe_ratio,roe,debt_ratio,revenue,profit,is_delisted,last_trade_date,asset_type "
                "FROM stocks WHERE code = ?",
                (code,),
            ).fetchone()
            stock = dict(stock_row) if stock_row else {'code': code}

            lookback = 420 if horizon == 'long' else 260
            daily_rows = cursor.execute(
                "SELECT trade_date,open,high,low,close,volume,amount,turnover,pct_change "
                "FROM daily_prices WHERE code = ? AND trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
                (code, trade_date, lookback),
            ).fetchall()
            daily_rows = [dict(r) for r in reversed(daily_rows)]

            if len(daily_rows) < 60:
                results.append({
                    'code': code,
                    'name': stock.get('name'),
                    'trade_date': trade_date,
                    'error': 'insufficient daily_prices history (<60 rows)',
                    'stock': stock,
                })
                continue

            closes = [float(r['close']) for r in daily_rows]
            highs = [float(r['high']) for r in daily_rows]
            lows = [float(r['low']) for r in daily_rows]
            volumes = [float(r.get('volume') or 0) for r in daily_rows]

            last = daily_rows[-1]
            last_close = float(last['close'])

            ma5 = _assistant_rules_sma(closes, 5)
            ma10 = _assistant_rules_sma(closes, 10)
            ma20 = _assistant_rules_sma(closes, 20)
            ma60 = _assistant_rules_sma(closes, 60)
            ma120 = _assistant_rules_sma(closes, 120) if len(closes) >= 120 else None
            atr14 = _assistant_rules_atr(highs, lows, closes, 14)
            rsi14 = _assistant_rules_rsi(closes, 14)

            hi20 = max(highs[-20:])
            lo10 = min(lows[-10:])
            lo20 = min(lows[-20:])
            hi55 = max(highs[-55:]) if len(highs) >= 55 else max(highs)
            lo20_exit = lo20

            vma5 = _assistant_rules_sma(volumes, 5)
            vma20 = _assistant_rules_sma(volumes, 20)
            vol_ratio = (vma5 / vma20) if (vma5 is not None and vma20 and vma20 != 0) else None

            weekly = _assistant_rules_weekly_bars(daily_rows)
            weekly_closes = [float(r['close']) for r in weekly]
            weekly_macd = _assistant_rules_macd(weekly_closes, 12, 26, 9)
            wk_hist = weekly_macd['hist'][-1] if weekly_macd and weekly_macd.get('hist') else None
            wk_macd = weekly_macd['macd'][-1] if weekly_macd and weekly_macd.get('macd') else None
            wk_sig = weekly_macd['signal'][-1] if weekly_macd and weekly_macd.get('signal') else None
            weekly_trend_up = (wk_hist is not None and wk_macd is not None and wk_sig is not None and wk_hist > 0 and wk_macd > wk_sig)

            # Fundamental facts
            pe = stock.get('pe_ratio')
            roe = stock.get('roe')
            debt = stock.get('debt_ratio')
            profit = stock.get('profit')
            revenue = stock.get('revenue')
            is_delisted = bool(stock.get('is_delisted')) if stock.get('is_delisted') is not None else False

            fund_ok = True
            fund_flags = []
            if is_delisted:
                fund_ok = False
                fund_flags.append('已退市')
            if profit is not None:
                try:
                    if float(profit) <= 0:
                        fund_flags.append('利润<=0')
                except Exception:
                    pass
            if roe is not None:
                try:
                    if float(roe) < 8:
                        fund_flags.append('ROE<8')
                except Exception:
                    pass
            if debt is not None:
                try:
                    if float(debt) > 70:
                        fund_flags.append('资产负债率>70')
                except Exception:
                    pass

            if horizon == 'long' and fund_flags:
                fund_ok = False

            facts = {
                'trade_date': trade_date,
                'close': round(last_close, 2),
                'pct_change': last.get('pct_change'),
                'ma5': round(ma5, 2) if ma5 is not None else None,
                'ma10': round(ma10, 2) if ma10 is not None else None,
                'ma20': round(ma20, 2) if ma20 is not None else None,
                'ma60': round(ma60, 2) if ma60 is not None else None,
                'ma120': round(ma120, 2) if ma120 is not None else None,
                'hi20': round(hi20, 2),
                'hi55': round(hi55, 2),
                'lo10': round(lo10, 2),
                'lo20': round(lo20, 2),
                'atr14': round(atr14, 4) if atr14 is not None else None,
                'atr14_pct': round((atr14 / last_close) * 100.0, 2) if (atr14 is not None and last_close) else None,
                'rsi14': round(rsi14, 2) if rsi14 is not None else None,
                'vol_ratio_5_20': round(vol_ratio, 3) if vol_ratio is not None else None,
                'weekly_macd_hist': round(wk_hist, 6) if wk_hist is not None else None,
                'weekly_macd': round(wk_macd, 6) if wk_macd is not None else None,
                'weekly_signal': round(wk_sig, 6) if wk_sig is not None else None,
                'weekly_trend_up': weekly_trend_up,
                'fundamentals': {
                    'pe_ratio': pe,
                    'pb_ratio': stock.get('pb_ratio'),
                    'roe': roe,
                    'debt_ratio': debt,
                    'revenue': revenue,
                    'profit': profit,
                    'flags': fund_flags,
                    'ok_for_horizon': fund_ok,
                }
            }

            trace = []

            ts_applicable = weekly_trend_up and (rsi14 is not None)
            ts_timing_ok = (rsi14 is not None and rsi14 < 40.0) if weekly_trend_up else False
            ts_entry_price = max(highs[-5:]) if len(highs) >= 5 else highs[-1]
            ts_entry_trigger = last_close > ts_entry_price

            ts_score = 0.0
            if ts_applicable:
                ts_score += 40.0
                if ts_timing_ok:
                    ts_score += 30.0
                    ts_score += max(0.0, min(30.0, 40.0 - float(rsi14 or 50.0)))
                if ts_entry_trigger:
                    ts_score += 10.0

            ts_trend_item = {
                'rule_id': 'elder.triple_screen.ts1.trend_filter.v1',
                'rule_name': SOURCES['elder_ts_trend']['title'],
                'source': SOURCES['elder_ts_trend'],
                'predicate': '(weekly.macd_hist > 0) AND (weekly.macd > weekly.signal)',
                'result': bool(weekly_trend_up),
                'evidence': {
                    'weekly_macd_hist': facts['weekly_macd_hist'],
                    'weekly_macd': facts['weekly_macd'],
                    'weekly_signal': facts['weekly_signal'],
                },
                'conclusion': '长周期趋势向上' if weekly_trend_up else '长周期趋势不向上',
            }
            ts_timing_item = {
                'rule_id': 'elder.triple_screen.ts2.timing.v1',
                'rule_name': SOURCES['elder_ts_timing']['title'],
                'source': SOURCES['elder_ts_timing'],
                'predicate': '(daily.rsi14 < 40)  # 上升趋势中的回调/超卖择时',
                'result': bool(ts_timing_ok),
                'evidence': {'rsi14': facts['rsi14']},
                'conclusion': '择时条件满足（偏回调）' if ts_timing_ok else '择时条件不满足',
            }
            ts_entry_item = {
                'rule_id': 'elder.triple_screen.ts3.entry.v1',
                'rule_name': SOURCES['elder_ts_entry']['title'],
                'source': SOURCES['elder_ts_entry'],
                'predicate': '(close > highest_high_5d)  # 转强入场触发',
                'result': bool(ts_entry_trigger),
                'evidence': {'close': facts['close'], 'highest_high_5d': round(ts_entry_price, 2)},
                'conclusion': '入场触发已出现' if ts_entry_trigger else '等待入场触发',
            }

            triple_screen = {
                'model_id': 'elder.triple_screen.long_only.v1',
                'model_name': '三重滤网（长周期趋势 + 中周期择时 + 短周期触发）',
                'applicable': bool(ts_applicable),
                'score': round(ts_score, 2),
                'conclusion': (
                    '适用：趋势向上，择时/触发待确认' if ts_applicable else '不适用：长周期趋势条件不满足'
                ),
                'why_steps': [
                    {
                        'source': SOURCES['elder_ts_trend'],
                        'condition': '周线 MACD 柱体>0 且 DIF>DEA',
                        'result': '趋势向上' if weekly_trend_up else '趋势不向上',
                        'evidence': ts_trend_item['evidence'],
                    },
                    {
                        'source': SOURCES['elder_ts_timing'],
                        'condition': '日线 RSI14 < 40（回调择时）',
                        'result': '满足' if ts_timing_ok else '不满足',
                        'evidence': ts_timing_item['evidence'],
                    },
                    {
                        'source': SOURCES['elder_ts_entry'],
                        'condition': '收盘价 > 5日最高价（转强触发）',
                        'result': '已触发' if ts_entry_trigger else '未触发',
                        'evidence': ts_entry_item['evidence'],
                    },
                ],
                'plan': {
                    'direction': 'long',
                    'entry': {
                        'type': 'trigger',
                        'trigger': f"收盘价突破 5日最高价（≈{round(ts_entry_price, 2)}）",
                    },
                    'risk': {
                        'stop_loss': f"跌破 10日最低价（≈{facts['lo10']}）则判定失效/止损",
                        'position_sizing': f"参考 ATR14（≈{facts['atr14']}）控制单笔风险",
                    },
                    'notes': '该模型为长周期趋势过滤，默认不做融券/做空。',
                },
            }

            if horizon == 'short':
                entry_n = 20
                exit_n = 10
                entry_high = hi20
                exit_low = lo10
            else:
                entry_n = 55
                exit_n = 20
                entry_high = hi55
                exit_low = lo20_exit

            turtle_applicable = True
            turtle_near_breakout = last_close >= entry_high * 0.97
            turtle_breakout = last_close > entry_high
            turtle_score = 0.0
            if turtle_near_breakout:
                turtle_score += 50.0
                turtle_score += min(30.0, max(0.0, (last_close / entry_high - 1.0) * 1000.0))
            if turtle_breakout:
                turtle_score += 20.0

            turtle_entry_item = {
                'rule_id': 'turtle.entry.channel_breakout.v1',
                'rule_name': SOURCES['turtle_entry']['title'],
                'source': SOURCES['turtle_entry'],
                'predicate': f'(close > highest_high_{entry_n}d)',
                'result': bool(turtle_breakout),
                'evidence': {'close': facts['close'], f'highest_high_{entry_n}d': round(entry_high, 2)},
                'conclusion': '突破入场成立' if turtle_breakout else '突破入场未成立',
            }
            turtle_exit_item = {
                'rule_id': 'turtle.exit.channel.v1',
                'rule_name': SOURCES['turtle_exit']['title'],
                'source': SOURCES['turtle_exit'],
                'predicate': f'(close < lowest_low_{exit_n}d)  # 退出信号',
                'result': bool(last_close < exit_low),
                'evidence': {'close': facts['close'], f'lowest_low_{exit_n}d': round(exit_low, 2)},
                'conclusion': '触发退出' if last_close < exit_low else '未触发退出',
            }

            turtle = {
                'model_id': f'turtle.channel_breakout.{entry_n}_{exit_n}.v1',
                'model_name': f'海龟通道突破（入场{entry_n}日 / 退出{exit_n}日）',
                'applicable': bool(turtle_applicable),
                'score': round(turtle_score, 2),
                'conclusion': '适用：接近/可能突破关键通道' if turtle_near_breakout else '适用但不临近突破位（赔率一般）',
                'why_steps': [
                    {
                        'source': SOURCES['turtle_entry'],
                        'condition': f'收盘价 > {entry_n}日最高价（突破入场）',
                        'result': '已突破' if turtle_breakout else ('接近突破' if turtle_near_breakout else '未接近'),
                        'evidence': turtle_entry_item['evidence'],
                    },
                    {
                        'source': SOURCES['turtle_exit'],
                        'condition': f'收盘价 < {exit_n}日最低价（退出信号）',
                        'result': '已触发退出' if last_close < exit_low else '未触发退出',
                        'evidence': turtle_exit_item['evidence'],
                    },
                ],
                'plan': {
                    'direction': 'long',
                    'entry': {
                        'type': 'stop',
                        'trigger': f"突破 {entry_n}日最高价（≈{round(entry_high, 2)}）上方入场",
                        'note': '可用突破价上方少量“买入止损单/条件单”模拟',
                    },
                    'risk': {
                        'stop_loss': f"跌破 {exit_n}日最低价（≈{round(exit_low, 2)}）则退出",
                        'position_sizing': f"参考 ATR14（≈{facts['atr14']}）设定每笔风险单位",
                    },
                    'notes': '该模型属于趋势跟随，核心在于“突破后不回撤则持有，回撤触发退出”。',
                },
            }

            fund_trace_item = {
                'rule_id': 'fundamental.quality_gate.v1',
                'rule_name': SOURCES['fund_quality']['title'],
                'source': SOURCES['fund_quality'],
                'predicate': 'profit>0 AND roe>=8 AND debt_ratio<=70  # 长线为硬约束，短/中为风险提示',
                'result': bool(fund_ok),
                'evidence': {
                    'profit': profit,
                    'roe': roe,
                    'debt_ratio': debt,
                    'flags': fund_flags,
                    'horizon': horizon,
                },
                'conclusion': '基本面通过' if fund_ok else f"基本面不通过/风险提示：{', '.join(fund_flags) if fund_flags else '缺字段'}",
            }

            candidates = []
            trace = []
            allow_ts = (enabled_models is None) or ('triple_screen' in enabled_models)
            allow_turtle = (enabled_models is None) or ('turtle' in enabled_models)
            if allow_ts:
                trace.extend([ts_trend_item, ts_timing_item, ts_entry_item])
                candidates.append(triple_screen)
            if allow_turtle:
                trace.extend([turtle_entry_item, turtle_exit_item])
                candidates.append(turtle)
            trace.append(fund_trace_item)
            if horizon == 'long' and not fund_ok:
                for m in candidates:
                    m['score'] = round(float(m.get('score') or 0) - 30.0, 2)
                    m['conclusion'] = f"{m.get('conclusion')}（长线基本面约束未通过，建议观望/降低仓位）"

            ranked = sorted(candidates, key=lambda x: float(x.get('score') or 0), reverse=True)
            selected = ranked[0] if ranked else None

            router_trace_item = {
                'rule_id': 'router.model_select.v1',
                'rule_name': SOURCES['model_select']['title'],
                'source': SOURCES['model_select'],
                'predicate': 'filter(applicable) then sort_by(score) desc',
                'result': True,
                'evidence': {
                    'ranked_models': [{'model_id': m['model_id'], 'score': m['score'], 'applicable': m['applicable']} for m in ranked],
                    'selected_model': selected['model_id'] if selected else None,
                },
                'conclusion': f"选择模型：{selected['model_id'] if selected else '—'}",
            }
            trace.append(router_trace_item)

            explanation_text = _assistant_rules_format_explanation(selected) if selected else '无可用模型'

            results.append({
                'code': code,
                'name': stock.get('name'),
                'trade_date': trade_date,
                'horizon': horizon,
                'stock': stock,
                'facts': facts,
                'models': ranked,
                'selected_model_id': selected['model_id'] if selected else None,
                'explanation_text': explanation_text,
                'trace': trace,
            })

        conn.close()
        resp_obj = {
            'request': {
                'codes': codes,
                'horizon': horizon,
                'models': enabled_models or ['triple_screen', 'turtle'],
                'requested_date': requested_date,
                'trade_date': trade_date,
            },
            'results': results,
        }

        try:
            run_id = save_rule_run(
                request_obj={
                    'codes': codes,
                    'horizon': horizon,
                    'requested_date': requested_date,
                },
                response_obj=resp_obj,
            )
            resp_obj['run_id'] = run_id
        except Exception:
            pass

        return safe_jsonify(resp_obj)
    except Exception as e:
        return jsonify({'error': f'assistant rules analyze failed: {str(e)}'}), 500


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
    runs = [r for r in (runs or []) if isinstance(r, dict)]
    runs = sorted(runs, key=lambda r: r.get('requested_at') or '', reverse=True)[:200]

    tmp_path = path.with_suffix(path.suffix + '.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(runs, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


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


def _parse_five_flags_run_summary_from_log(log_file: str) -> dict:
    """
    Best-effort parse of summary stats from a per-run log file.
    Expected markers (printed by scripts/run_five_flags_pool_screening.py):
      - Total stocks processed: N
      - Total matches found: N
      - Total failed: N
    """
    if not log_file:
        return {}
    try:
        path = Path(str(log_file))
    except Exception:
        return {}
    if not path.exists():
        return {}

    summary = {}
    lines = _read_log_tail(path, tail=240)
    for raw in lines:
        line = (raw or '').strip()
        if not line:
            continue

        if 'Total stocks processed:' in line:
            try:
                summary['total_stocks'] = int(line.split('Total stocks processed:', 1)[1].strip())
            except Exception:
                pass
        elif 'Total matches found:' in line:
            try:
                summary['total_matches'] = int(line.split('Total matches found:', 1)[1].strip())
            except Exception:
                pass
        elif 'Total failed:' in line:
            try:
                summary['failed_stocks'] = int(line.split('Total failed:', 1)[1].strip())
            except Exception:
                pass

    return summary


def _five_flags_daily_scheduler_state_path():
    return DASHBOARD_DIR.parent / 'data' / 'five_flags_daily_scheduler_state.json'


def _five_flags_default_phase_profile_path():
    return DASHBOARD_DIR.parent / 'config' / 'screeners' / 'market_phase_profiles.json'


def _resolve_phase_profile_path(path_str=None):
    base_dir = (DASHBOARD_DIR.parent / 'config' / 'screeners').resolve()
    if not path_str:
        return _five_flags_default_phase_profile_path()
    candidate = Path(str(path_str))
    resolved = candidate.resolve() if candidate.is_absolute() else (DASHBOARD_DIR.parent / candidate).resolve()
    try:
        resolved.relative_to(base_dir)
    except ValueError:
        raise ValueError('phase_profile must be under config/screeners')
    if resolved.suffix.lower() != '.json':
        raise ValueError('phase_profile must be a .json file')
    return resolved


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
    conn = get_stock_db_connection()
    try:
        return compute_five_flags_unprocessed_data_readiness(conn)
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
            item_status = item.get('status')
            if item_status not in ('started', 'failed'):
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
                else:
                    if item_status == 'failed' and item.get('error') == 'run failed':
                        item['error'] = None
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


def _normalize_five_flags_job_signature(
    *,
    source,
    pool_ids=None,
    max_workers=None,
    retry_of=None,
    snapshot_id=None,
    flow_config=None,
    market_phase=None,
    phase_profile=None,
    profile_slot='active',
    calibration_note=None,
    as_of_date=None,
):
    normalized_pool_ids = sorted({int(pid) for pid in (pool_ids or [])})
    normalized_flow_config = None
    if flow_config is not None:
        normalized_flow_config = json.dumps(flow_config, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return {
        'source': source or 'manual_run',
        'pool_ids': normalized_pool_ids,
        'max_workers': int(max_workers) if max_workers is not None else None,
        'retry_of': str(retry_of) if retry_of else None,
        'snapshot_id': str(snapshot_id) if snapshot_id else None,
        'flow_config': normalized_flow_config,
        'market_phase': market_phase or 'default',
        'phase_profile': str(phase_profile) if phase_profile else None,
        'profile_slot': profile_slot or 'active',
        'calibration_note': calibration_note or None,
        'as_of_date': as_of_date or None,
    }


def _find_active_duplicate_five_flags_job(signature: dict):
    with FIVE_FLAGS_QUEUE_LOCK:
        queue_items = _refresh_five_flags_queue_status(lock_held=True)
        candidate_items = [x for x in queue_items if x.get('status') in ('queued', 'started')]
        if not candidate_items:
            return None
        matched_items = []
        for item in candidate_items:
            item_signature = _normalize_five_flags_job_signature(
                source=item.get('source'),
                pool_ids=item.get('pool_ids') or [],
                max_workers=item.get('max_workers'),
                retry_of=item.get('retry_of'),
                snapshot_id=item.get('snapshot_id'),
                flow_config=item.get('flow_config'),
                market_phase=item.get('market_phase'),
                phase_profile=item.get('phase_profile'),
                profile_slot=item.get('profile_slot') or 'active',
                calibration_note=item.get('calibration_note'),
                as_of_date=item.get('as_of_date'),
            )
            if item_signature == signature:
                matched_items.append(item)
        if not matched_items:
            return None

        matched_items = sorted(matched_items, key=lambda x: x.get('requested_at') or '')
        primary = next((x for x in matched_items if x.get('status') == 'started'), None)
        if not primary:
            primary = matched_items[0]

        duplicate_queued_ids = {
            x.get('job_id')
            for x in matched_items
            if x.get('job_id') != primary.get('job_id') and x.get('status') == 'queued'
        }
        if duplicate_queued_ids:
            queue_items = [
                x for x in queue_items
                if x.get('job_id') not in duplicate_queued_ids
            ]
            _save_five_flags_queue(queue_items)
        return primary


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

        def _infer_final_status_from_log(log_path: str):
            if not log_path:
                return None, {}
            try:
                p = Path(str(log_path))
            except Exception:
                return None, {}
            if not p.exists():
                return None, {}
            tail_lines = _read_log_tail(p, tail=320)
            tail_text = '\n'.join(tail_lines)
            has_success_marker = 'Five Flags Pool Screening completed at' in tail_text
            has_traceback = 'Traceback (most recent call last):' in tail_text
            has_module_missing = 'ModuleNotFoundError' in tail_text
            if has_success_marker and not (has_traceback or has_module_missing):
                return 'completed', _parse_five_flags_run_summary_from_log(str(p))
            if has_traceback or has_module_missing:
                return 'failed', _parse_five_flags_run_summary_from_log(str(p))
            return None, _parse_five_flags_run_summary_from_log(str(p))

        if status in ('running', 'accepted'):
            pid = run.get('pid')
            if pid and _is_pid_running(pid):
                if status != 'running':
                    run['status'] = 'running'
                    changed = True
            else:
                if status != 'completed' and status != 'failed':
                    log_file = run.get('log_file')
                    inferred, parsed = _infer_final_status_from_log(log_file)
                    run['status'] = inferred or 'failed'
                    run['completed_at'] = run.get('completed_at') or now_ts
                    if log_file:
                        if isinstance(parsed, dict) and parsed:
                            for key, value in parsed.items():
                                if run.get(key) != value:
                                    run[key] = value
                                    changed = True
                    changed = True
        elif status == 'failed':
            # Backward-compatible correction: some runs may be marked failed due to non-fatal ERROR logs.
            log_file = run.get('log_file')
            inferred, parsed = _infer_final_status_from_log(log_file)
            if inferred == 'completed':
                run['status'] = 'completed'
                run['completed_at'] = run.get('completed_at') or now_ts
                changed = True
            if log_file and isinstance(parsed, dict) and parsed:
                for key, value in parsed.items():
                    if run.get(key) != value:
                        run[key] = value
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
        force_run = bool(payload.get('force_run', False) or payload.get('force', False))
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

        def _current_phase_profile_version():
            try:
                profile_path = _resolve_phase_profile_path(phase_profile)
                doc = _load_phase_profile_doc(profile_path)
                metadata = doc.get('metadata') if isinstance(doc.get('metadata'), dict) else {}
                v = metadata.get('version')
                return str(v) if v else None
            except Exception:
                return None

        def _last_completed_profile_version():
            try:
                runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
                target_phase = market_phase or 'default'
                for run in sorted(runs, key=lambda r: r.get('requested_at') or '', reverse=True):
                    if run.get('status') != 'completed':
                        continue
                    if (run.get('market_phase') or 'default') != target_phase:
                        continue
                    if (run.get('profile_slot') or 'active') != profile_slot:
                        continue
                    requested_profile = phase_profile
                    if not requested_profile:
                        requested_profile = str(_resolve_phase_profile_path(None))
                    if (run.get('phase_profile') or str(_resolve_phase_profile_path(None))) != requested_profile:
                        continue
                    pv = run.get('profile_version')
                    return str(pv) if pv else None
                return None
            except Exception:
                return None

        # For default manual run (no explicit pool_ids), apply readiness guard unless forced.
        if not normalized_pool_ids and not dry_run and not force_run:
            readiness = _check_five_flags_unprocessed_data_readiness()
            if not readiness.get('ready'):
                if readiness.get('reason') == 'up_to_date':
                    current_v = _current_phase_profile_version()
                    last_v = _last_completed_profile_version()
                    return safe_jsonify({
                        'status': 'skipped',
                        'accepted': False,
                        'reason': readiness.get('reason'),
                        'guard': readiness,
                        'profile_version_current': current_v,
                        'profile_version_last_completed': last_v,
                        'hint': 'set force_run=true to run despite up_to_date'
                    }), 200
                else:
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

        request_signature = _normalize_five_flags_job_signature(
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
        duplicate_job = _find_active_duplicate_five_flags_job(request_signature)
        if duplicate_job:
            return safe_jsonify({
                'status': 'skipped_duplicate',
                'accepted': False,
                'queue_status': duplicate_job.get('status'),
                'existing_job_id': duplicate_job.get('job_id'),
                'existing_run_id': duplicate_job.get('run_id'),
                'queued_pools': len(normalized_pool_ids),
                'market_phase': market_phase,
                'phase_profile': phase_profile,
                'profile_slot': profile_slot,
                'calibration_note': calibration_note,
                'as_of_date': as_of_date
            }), 200

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
