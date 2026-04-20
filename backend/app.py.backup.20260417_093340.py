#!/usr/bin/env python3
"""
Flask Backend API for Trading Screener Dashboard
"""
import os
import sys
import sqlite3
import traceback
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, date
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from functools import wraps
import json
import math

class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles NaN, Infinity, -Infinity by converting to null"""
    def encode(self, obj):
        # Recursively walk through and replace NaN/Infinity
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

# Load environment variables from config/.env
# __file__ is backend/app.py, so parent is backend, parent.parent is NeoTrade2
env_file = Path('/Users/mac/NeoTrade2/config/.env')
if env_file.exists():
    load_dotenv(env_file, override=True)  # Use override=True to force override existing env vars
    print(f"[DEBUG] Loading .env from: {env_file}")
else:
    print(f"[WARNING] .env file not found at: {env_file}")

# Add dashboard to path
DASHBOARD_DIR = Path(__file__).parent
# 确保_WORKSPACE_ROOT指向项目根目录（NeoTrade2/）
if os.environ.get("WORKSPACE_ROOT"):
    _WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT"))
else:
    # 如果没有设置环境变量，从app.py的位置推导
    # backend/app.py -> backend -> NeoTrade2
    _WORKSPACE_ROOT = DASHBOARD_DIR.parent

sys.path.insert(0, str(DASHBOARD_DIR))
sys.path.insert(0, str(_WORKSPACE_ROOT))  # Add workspace root

from models import (
    init_db, get_all_screeners, get_screener, get_runs, get_run,
    get_results, get_results_by_date, log_access, get_access_stats
)
# screeners模块是backend目录的screeners.py
import importlib.util
spec = importlib.util.spec_from_file_location("screeners_module", DASHBOARD_DIR / "screeners.py")
screeners_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screeners_module)

register_discovered_screeners = screeners_module.register_discovered_screeners
run_screener_subprocess = screeners_module.run_screener_subprocess
get_stock_data_for_chart = screeners_module.get_stock_data_for_chart
create_screener_file = screeners_module.create_screener_file
update_screener_file = screeners_module.update_screener_file
delete_screener_file = screeners_module.delete_screener_file

from excel_upload import handle_excel_upload
from strategy_management import strategy_bp  # Import strategy blueprint

# 简单密码配置 - 从环境变量读取，无默认值
DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')
print(f"[DEBUG] DASHBOARD_PASSWORD loaded: {DASHBOARD_PASSWORD[:10]}..." if DASHBOARD_PASSWORD else "[DEBUG] DASHBOARD_PASSWORD is None")
if not DASHBOARD_PASSWORD:
    raise ValueError("DASHBOARD_PASSWORD environment variable is required")

def check_auth(username, password):
    """验证密码（只验证密码，用户名随意）"""
    return password == DASHBOARD_PASSWORD

def authenticate():
    """返回 401 响应要求认证"""
    resp = Response(
        '请输入密码访问 Dashboard',
        401,
        {'WWW-Authenticate': 'Basic realm="NeoTrade Dashboard"'}
    )
    return resp

def require_auth(f):
    """装饰器：要求认证"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

app = Flask(__name__, static_folder=None)  # Disable default static folder, we handle it manually

# Enable CORS with restricted origins for security
# Only HTTPS for external domains to prevent mixed content issues
CORS_ORIGINS = [
    'http://localhost:5173',    # Vite dev server default
    'http://localhost:3000',    # Alternative dev server
    'http://127.0.0.1:5173',
    'http://127.0.0.1:3000',
    'https://neotrade.cpolar.cn',  # Cpolar subdomain tunnel
    'https://neiltrade.cloud',      # Cpolar custom domain
]
CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

# DEBUG: Log CORS origins to verify configuration
print(f"[DEBUG] CORS Origins (NO HTTP CPOLAR): {CORS_ORIGINS}")

# 为所有路由添加认证（除了健康检查）
@app.before_request
def before_request():
    # 健康检查端点不需要认证
    if request.path == '/api/health':
        return None

    # 临时调试端点不需要认证
    if request.path == '/api/debug-auth':
        return None

    # 监控端点不需要认证
    if request.path.startswith('/api/monitor'):
        return None

    # 检查是否为本地请求（跳过认证）
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    local_ips = ['127.0.0.1', '::1', 'localhost']
    is_local = (ip in local_ips or
                ip.startswith('192.168.') or
                ip.startswith('10.') or
                any(ip.startswith(f'172.{x}.') for x in range(16, 32)))

    # 调试输出
    print(f"[AUTH] Request: {request.path}, IP: {ip}, is_local: {is_local}")

    # 注意：本地请求不再跳过认证，确保 Basic Auth 在所有环境下都工作

    # 记录访问（只记录主页面路由，排除 API、静态资源和健康检查）
    # 只记录根路径 / 和明确的页面路径，排除 /assets/, /favicon 等
    if request.path == '/' or (not request.path.startswith('/api/') and
                               not request.path.startswith('/assets/') and
                               not request.path.startswith('/favicon') and
                               not request.path.endswith('.svg') and
                               not request.path.endswith('.ico')):
        try:
            log_access(ip, request.user_agent.string, request.path)
        except:
            pass  # Don't block request if logging fails

    # 非本地请求需要认证
# Serve index.html at root - NO CACHE
@app.route('/')
def index():
    response = send_from_directory(DASHBOARD_DIR.parent / 'frontend/dist', 'index.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Serve assets - with cache busting
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    response = send_from_directory(DASHBOARD_DIR.parent / 'frontend/dist/assets', filename)
    # Assets have hash in filename, so we can cache them long-term
    if '.' in filename and filename.split('.')[-2] and len(filename.split('.')[-2]) > 8:
        # Hashed assets - cache for 1 year
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    else:
        # Non-hashed assets - no cache
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

# Serve favicon and other root files
@app.route('/favicon.svg')
def serve_favicon():
    return send_from_directory(DASHBOARD_DIR.parent / 'frontend/dist', 'favicon.svg')

@app.route('/icons.svg')
def serve_icons():
    return send_from_directory(DASHBOARD_DIR.parent / 'frontend/dist', 'icons.svg')

# Catch-all route for React Router - must be last
@app.route('/<path:path>')
def catch_all(path):
    # DEBUG: Log all non-API requests to diagnose 404s
    print(f"[DEBUG] catch_all path: {path}, startswith api/: {path.startswith('api/')}")

    # Don't catch API routes
    if path.startswith('api/'):
        print(f"[DEBUG] Returning 404 for API path: {path}")
        return jsonify({'error': 'Not found'}), 404
    # For all other routes, serve index.html (React Router handles client-side routing)
    print(f"[DEBUG] Serving index.html for path: {path}")
    return send_from_directory(DASHBOARD_DIR.parent / 'frontend/dist', 'index.html')

# Initialize database on startup
init_db()
register_discovered_screeners()

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    import sys
    import logging
    logging.basicConfig(level=logging.DEBUG)
    data_date = None
    try:
        print(f"[DEBUG] Connecting to stock_data.db at: {_STOCK_DB}")
        conn = sqlite3.connect(str(_STOCK_DB))
        row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
        conn.close()
        if row and row[0]:
            data_date = row[0]
    except Exception as e:
        print(f"[DEBUG] Error connecting to stock_data.db: {e}")
        pass
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat(), 'data_date': data_date})

@app.route('/api/debug-auth', methods=['GET'])
def debug_auth():
    """调试认证端点"""
    import sys
    import logging
    logging.basicConfig(level=logging.DEBUG)
    auth = request.authorization
    debug_info = {
        'has_auth': auth is not None,
        'auth_type': auth.type if auth else None,
        'username': auth.username if auth else None,
        'password_provided': auth.password is not None if auth else False,
        'password_length': len(auth.password) if auth and auth.password else 0,
        'env_password_length': len(DASHBOARD_PASSWORD) if DASHBOARD_PASSWORD else 0,
        'password_match': (auth.password == DASHBOARD_PASSWORD) if auth and auth.password else False
    }
    print(f"[DEBUG-AUTH] Request auth object: {auth}", flush=True)
    print(f"[DEBUG-AUTH] Debug info: {debug_info}", flush=True)
    return jsonify(debug_info)

# Module definitions for categorization
MODULES = {
    'screeners': {
        'title': 'Technical Screeners',
        'items': [
            'lao_ya_tou_zhou_xian_screener',
            'jin_feng_huang_screener',
            'er_ban_hui_tiao_screener',
            'zhang_ting_bei_liang_yin_screener',
            'yin_feng_huang_screener',
            'shi_pan_xian_screener',
            'breakout_20day_screener',
            'breakout_main_screener',
            'daily_hot_cold_screener',
            'ashare_21_screener'
        ]
    },

    'jobs': {
        'title': 'Manual Jobs',
        'items': [],
        'dependencies': {}
    }
}

# Screener endpoints
@app.route('/api/screeners', methods=['GET'])
@require_auth
def list_screeners():
    """List all available screeners with categories"""
    screeners = get_all_screeners()
    
    # Add category to each screener
    for s in screeners:
        name = s['name']
        if name in MODULES['screeners']['items']:
            s['category'] = 'screener'
            s['category_label'] = 'Technical'
            s['schedule'] = 'On-demand'
            s['category_label'] = 'Cron Task'
        elif name in MODULES['jobs']['items']:
            s['category'] = 'job'
            s['category_label'] = 'Manual Job'
            s['schedule'] = 'Manual'
            s['dependency'] = MODULES['jobs']['dependencies'].get(name)
        else:
            s['category'] = 'other'
            s['category_label'] = 'Other'
            s['schedule'] = 'Unknown'
    
    return jsonify({'screeners': screeners, 'modules': MODULES})

@app.route('/api/screeners/<name>', methods=['GET'])
@require_auth
@require_auth
def get_screener_detail(name):
    """Get screener details"""
    screener = get_screener(name)
    if not screener:
        return jsonify({'error': 'Screener not found'}), 404
    
    # Read the source file for display
    try:
        with open(screener['file_path'], 'r') as f:
            source_code = f.read()
    except Exception as e:
        source_code = f"Error reading file: {e}"
    
    return jsonify({
        'screener': screener,
        'source_code': source_code
    })

@app.route('/api/screeners/<name>/run', methods=['POST'])
@require_auth
def run_screener(name):
    """Run a screener"""
    data = request.get_json() or {}
    run_date = data.get('date', date.today().isoformat())
    
    screener = get_screener(name)
    if not screener:
        return jsonify({'error': 'Screener not found'}), 404
    
    # Run the screener
    try:
        result = run_screener_subprocess(name, run_date)
    except Exception as _e:
        import traceback as _tb
        _msg = _tb.format_exc()
        print(f"[ERROR] run_screener_subprocess CRASHED:\n{_msg}")
        return jsonify({'success': False, 'error': str(_e), 'message': f'Screener crashed: {_e}'}), 500

    if result['success']:
        return jsonify({
            'success': True,
            'run_id': result['run_id'],
            'stocks_found': result['stocks_found'],
            'message': f"Screener completed. Found {result['stocks_found']} stocks."
        })
    else:
        print(f"[ERROR] Screener {name} failed: {result.get('error')}\n{result.get('traceback','')}")
        return jsonify({
            'success': False,
            'error': result['error'],
            'message': f"Screener failed: {result['error']}"
        }), 500

# Results endpoints
@app.route('/api/runs', methods=['GET'])
@require_auth
def list_runs():
    """List historical runs"""
    screener_name = request.args.get('screener')
    limit = request.args.get('limit', 50, type=int)
    
    runs = get_runs(screener_name=screener_name, limit=limit)
    return jsonify({'runs': runs})

@app.route('/api/results', methods=['GET'])
@require_auth
def get_results_endpoint():
    """Get results by screener and date"""
    screener_name = request.args.get('screener')
    run_date = request.args.get('date')
    
    if not screener_name or not run_date:
        return jsonify({'error': 'Missing screener or date parameter'}), 400
    
    results = get_results_by_date(screener_name, run_date)
    
    if results is None:
        # Debug: check what runs exist for this screener
        all_runs = get_runs(screener_name=screener_name, limit=5)
        print(f"DEBUG: No run found for {screener_name} on {run_date}")
        print(f"DEBUG: Recent runs for this screener: {[r['run_date'] for r in all_runs]}")
        return jsonify({'error': f'No run found for {screener_name} on {run_date}'}), 404
    
    print(f"DEBUG: Found {len(results)} results for {screener_name} on {run_date}")
    
    # Special handling for daily_hot_cold_screener - group by type
    if screener_name == 'daily_hot_cold_screener':
        hot_results = []
        cold_results = []
        
        print(f"DEBUG: Processing {len(results)} results for hot/cold grouping")
        
        for result in results:
            extra = result.get('extra_data', {}) or {}
            stock_type = extra.get('_category', extra.get('_type', extra.get('type', '')))
            pct_change = result.get('pct_change', 0) or extra.get('pct_change', 0)
            
            print(f"DEBUG: {result.get('stock_code')} - type={stock_type}, pct_change={pct_change}")
            
            if stock_type == 'hot' or (not stock_type and pct_change >= 5):
                hot_results.append(result)
            elif stock_type == 'cold' or (not stock_type and pct_change <= -5):
                cold_results.append(result)
        
        print(f"DEBUG: Grouped into {len(hot_results)} hot, {len(cold_results)} cold")
        
        return safe_jsonify({
            'screener': screener_name,
            'date': run_date,
            'count': len(results),
            'hot_count': len(hot_results),
            'cold_count': len(cold_results),
            'hot': hot_results,
            'cold': cold_results
        })
    
    return safe_jsonify({
        'screener': screener_name,
        'date': run_date,
        'count': len(results),
        'results': results
    })

@app.route('/api/stock/<code>/chart', methods=['GET'])
@require_auth
def get_stock_chart(code):
    """Get stock price data for K-line chart"""
    days = request.args.get('days', 60, type=int)
    
    data = get_stock_data_for_chart(code, days)
    
    if data is None:
        return jsonify({'error': 'Stock data not found'}), 404
    
    return jsonify({
        'code': code,
        'days': len(data),
        'data': data
    })

@app.route('/api/calendar', methods=['GET'])
@require_auth
def get_calendar_data():
    """Get calendar view data - runs grouped by date"""
    runs = get_runs(limit=365)  # Last year
    
    # Group by date
    calendar = {}
    for run in runs:
        date_str = run['run_date']
        if date_str not in calendar:
            calendar[date_str] = {
                'date': date_str,
                'screeners': [],
                'total_stocks': 0
            }
        calendar[date_str]['screeners'].append({
            'name': run['screener_name'],
            'status': run['status'],
            'stocks_found': run['stocks_found']
        })
        calendar[date_str]['total_stocks'] += run['stocks_found']
    
    return jsonify({
        'calendar': list(calendar.values())
    })

# CRUD Operations for Screeners/Tasks/Jobs
@app.route('/api/screeners', methods=['POST'])
@require_auth
def create_screener():
    """Create a new screener/task/job"""
    data = request.get_json() or {}
    
    name = data.get('name', '').strip()
    display_name = data.get('display_name', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', 'screener')  # screener, cron, job
    code_content = data.get('code')
    
    if not name or not display_name:
        return jsonify({'error': 'Name and display_name are required'}), 400
    
    # Validate name (alphanumeric and underscore only)
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
        return jsonify({'error': 'Name must start with letter and contain only letters, numbers, and underscores'}), 400
    
    try:
        screener = create_screener_file(name, display_name, description, category, code_content)
        return jsonify({
            'success': True,
            'screener': screener,
            'message': f'{category.title()} "{display_name}" created successfully'
        })
    except FileExistsError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/screeners/<name>', methods=['PUT'])
@require_auth
def update_screener_endpoint(name):
    """Update an existing screener/task/job"""
    data = request.get_json() or {}
    
    code_content = data.get('code')
    display_name = data.get('display_name')
    description = data.get('description')
    
    if not code_content:
        return jsonify({'error': 'Code content is required'}), 400
    
    try:
        result = update_screener_file(name, code_content, display_name, description)
        return jsonify({
            'success': True,
            'message': f'"{name}" updated successfully'
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/screeners/<name>', methods=['DELETE'])
@require_auth
def delete_screener_endpoint(name):
    """Delete a screener/task/job"""
    try:
        result = delete_screener_file(name)
        return jsonify({
            'success': True,
            'message': f'"{name}" deleted successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== Screener Configuration Management ==========
from config_loader import ConfigLoader
from validators import validate_screener_config_update
from docstring_updater import DocstringUpdater
import re

def snake_to_camel(s: str) -> str:
    """Convert snake_case to CamelCase, handling numeric prefixes correctly.

    Examples:
        'breakout_20day' -> 'Breakout20Day'
        'er_ban_hui_tiao' -> 'ErBanHuiTiao'
    """
    def capitalize_word(word: str) -> str:
        if not word:
            return word
        # Find first alphabetical character and capitalize it
        for i, char in enumerate(word):
            if char.isalpha():
                return word[:i] + char.upper() + word[i+1:]
        # No alphabetical characters, return as is
        return word

    return ''.join(capitalize_word(word) for word in s.split('_'))

def get_screener_schema(name: str) -> dict:
    """Get screener parameter schema by dynamically importing the screener class"""
    print(f"[DEBUG] get_screener_schema called with name: {name}")
    import sys
    import re
    from pathlib import Path

    try:
        # Add screeners directory to sys.path temporarily
        screeners_dir = str(DASHBOARD_DIR.parent / 'screeners')
        if screeners_dir not in sys.path:
            sys.path.insert(0, screeners_dir)
            print(f"[DEBUG] Added to sys.path: {screeners_dir}")

        # Check which module file exists
        module_file_v1 = Path(screeners_dir) / f'{name}.py'
        module_file_v2 = Path(screeners_dir) / f'{name}_screener.py'

        # Determine the correct module name
        if module_file_v1.exists():
            module_name = name
            print(f"[DEBUG] Using module name: {module_name} (file exists)")
        elif module_file_v2.exists():
            module_name = f'{name}_screener'
            print(f"[DEBUG] Using module name: {module_name} (file exists)")
        else:
            print(f"[DEBUG] Module file not found for {name}, trying standard pattern")
            module_name = f'{name}_screener'

        print(f"[DEBUG] Attempting to import module: {module_name}")

        module = __import__(module_name)
        print(f"[DEBUG] Module imported successfully: {module}")

        # Find all Screener classes in the module
        screener_classes = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and attr_name.endswith('Screener'):
                screener_classes.append(attr_name)

        print(f"[DEBUG] Found Screener classes: {screener_classes}")

        # Try to find the most appropriate class
        screener_class = None

        # Method 1: Try the standard pattern first
        standard_class = snake_to_camel(name) + 'Screener'
        if standard_class in screener_classes:
            screener_class = getattr(module, standard_class)
            print(f"[DEBUG] Using standard class: {standard_class}")

        # Method 2: If not found, try the name as-is converted to CamelCase
        elif not screener_class:
            camel_class = snake_to_camel(name)
            if f"{camel_class}Screener" in screener_classes:
                screener_class = getattr(module, f"{camel_class}Screener")
                print(f"[DEBUG] Using camel class: {camel_class}Screener")
            elif camel_class in screener_classes:
                screener_class = getattr(module, camel_class)
                print(f"[DEBUG] Using direct camel class: {camel_class}")

        # Method 3: If still not found, just take the first Screener class
        elif not screener_class and screener_classes:
            screener_class = getattr(module, screener_classes[0])
            print(f"[DEBUG] Using first available class: {screener_classes[0]}")

        print(f"[DEBUG] Final screener class: {screener_class}")

        if screener_class and hasattr(screener_class, 'get_parameter_schema'):
            schema = screener_class.get_parameter_schema()
            print(f"[DEBUG] Loaded schema for {name}: {list(schema.keys())}")
            return schema
        else:
            print(f"[DEBUG] Screener class or get_parameter_schema not found")

    except Exception as e:
        print(f"[ERROR] Could not get schema for {name}: {e}")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

    return {}

@app.route('/api/screeners/<name>/config', methods=['GET'])
def get_screener_config_endpoint(name):
    """Get screener configuration"""
    try:
        # Load config
        config = ConfigLoader.load_config(name)
        if not config:
            return jsonify({'error': f'Screener config not found: {name}'}), 404

        # Get schema
        schema = get_screener_schema(name)

        return jsonify({
            'success': True,
            'config': config,
            'schema': schema
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/screeners/<name>/config', methods=['PUT'])
def update_screener_config_endpoint(name):
    """Update screener configuration"""
    print(f"[DEBUG] update_screener_config_endpoint called with name: {name}")
    try:
        data = request.get_json()
        print(f"[DEBUG] Request data received: {data}")

        # Validate request
        is_valid, error_msg, validated_data = validate_screener_config_update(data)
        print(f"[DEBUG] Validation result: valid={is_valid}, error={error_msg}")
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        # Get schema for validation
        print(f"[DEBUG] Getting schema for screener: {name}")
        schema = get_screener_schema(name)
        print(f"[DEBUG] Schema loaded: {list(schema.keys()) if schema else 'None'}")

        # Validate parameters against schema
        if 'parameters' in validated_data:
            print(f"[DEBUG] Validating parameters: {list(validated_data['parameters'].keys())}")

            # Extract just the 'value' fields from parameter objects
            parameter_values = {}
            for param_name, param_obj in validated_data['parameters'].items():
                if isinstance(param_obj, dict) and 'value' in param_obj:
                    parameter_values[param_name] = param_obj['value']
                else:
                    # If it's already a simple value, use it directly
                    parameter_values[param_name] = param_obj

            print(f"[DEBUG] Extracted parameter values: {parameter_values}")
            print(f"[DEBUG] Schema: {list(schema.keys())}")

            all_valid, param_errors = ConfigLoader.validate_parameters(
                parameter_values,
                schema
            )
            print(f"[DEBUG] Parameter validation result: valid={all_valid}, errors={param_errors}")
            if not all_valid:
                return jsonify({
                    'error': 'Parameter validation failed',
                    'errors': param_errors
                }), 400

        # Load current config
        print(f"[DEBUG] Loading current config for: {name}")
        current_config = ConfigLoader.load_config(name)
        if not current_config:
            print(f"[ERROR] Current config not found for: {name}")
            return jsonify({'error': f'Screener config not found: {name}'}), 404

        # Build updated config
        updated_config = current_config.copy()
        if 'display_name' in validated_data:
            updated_config['display_name'] = validated_data['display_name']
        if 'description' in validated_data:
            updated_config['description'] = validated_data['description']
        if 'category' in validated_data:
            updated_config['category'] = validated_data['category']
        if 'parameters' in validated_data:
            # Use the extracted parameter values (simple values, not objects)
            for param_name, param_value in parameter_values.items():
                if param_name in updated_config['parameters']:
                    updated_config['parameters'][param_name]['value'] = param_value

        # Save config
        print(f"[DEBUG] Saving config for: {name}")
        success, new_version = ConfigLoader.save_config(
            name,
            updated_config,
            schema,
            change_summary=validated_data['change_summary'],
            changed_by=validated_data['updated_by']
        )
        print(f"[DEBUG] Save result: success={success}, new_version={new_version}")

        if not success:
            print(f"[ERROR] Config save failed for {name}")
            return jsonify({'error': 'Failed to save config'}), 500

        # Optionally update docstring
        # success, msg = DocstringUpdater.update_screener_docstring(name, updated_config, schema)

        return jsonify({
            'success': True,
            'message': 'Configuration updated successfully',
            'version': new_version
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] Failed to update config for {name}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ========== Monitoring Area Endpoints ==========

@app.route('/api/monitor/lyt-pool', methods=['GET'])
def get_lyt_pool_status():
    """Get LYT pool status for monitoring area"""
    print(f"[DEBUG] get_lyt_pool_status called")
    try:
        import sqlite3
        from pathlib import Path

        db_path = Path('/Users/mac/NeoTrade2/data/stock_data.db')
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get pool size
        cursor.execute('SELECT COUNT(*) as count FROM lao_ya_tou_pool')
        pool_size = cursor.fetchone()['count']

        # Get signal distribution
        cursor.execute('''
            SELECT current_signal, COUNT(*) as count
            FROM lao_ya_tou_pool
            GROUP BY current_signal
        ''')
        signal_rows = cursor.fetchall()
        signal_distribution = {
            'signal_1': 0,
            'signal_2': 0,
            'signal_3': 0
        }
        for row in signal_rows:
            signal = row['current_signal']
            if signal == 'signal_1':
                signal_distribution['signal_1'] = row['count']
            elif signal == 'signal_2':
                signal_distribution['signal_2'] = row['count']
            elif signal == 'signal_3':
                signal_distribution['signal_3'] = row['count']

        # Get recent entries (last 10)
        cursor.execute('''
            SELECT code, name, entry_date, current_signal, last_screened_date
            FROM lao_ya_tou_pool
            ORDER BY entry_date DESC
            LIMIT 10
        ''')
        recent_entries = [
            {
                'code': row['code'],
                'name': row['name'],
                'entry_date': row['entry_date'],
                'current_signal': row['current_signal'],
                'last_screened_date': row['last_screened_date']
            }
            for row in cursor.fetchall()
        ]

        # Get recent updates (signal changes in last 7 days, last 10)
        cursor.execute('''
            SELECT p1.code, p1.name, p1.current_signal as new_signal,
                   p1.entry_date as change_date
            FROM lao_ya_tou_pool p1
            WHERE p1.last_updated > date('now', '-7 days')
            ORDER BY p1.last_updated DESC
            LIMIT 10
        ''')
        recent_updates = [
            {
                'code': row['code'],
                'name': row['name'],
                'new_signal': row['new_signal'],
                'change_date': row['change_date']
            }
            for row in cursor.fetchall()
        ]

        # Get last update timestamp
        cursor.execute('SELECT MAX(last_updated) as last_update FROM lao_ya_tou_pool')
        last_update_row = cursor.fetchone()
        last_update = last_update_row['last_update'] if last_update_row['last_update'] else None

        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'pool_size': pool_size,
                'signal_distribution': signal_distribution,
                'recent_entries': recent_entries,
                'recent_updates': recent_updates,
                'last_update': last_update
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitor/pool-screeners', methods=['GET'])
def get_pool_screeners():
    """Get pool screeners monitoring results"""
    try:
        import sqlite3
        from pathlib import Path

        db_path = Path('/Users/mac/NeoTrade2/data/stock_data.db')
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get screener types (LYT and pool screeners)
        cursor.execute('''
            SELECT id, code, display_name
            FROM screener_types
            WHERE code IN (
                'lao_ya_tou_zhou_xian_screener',
                'er_ban_hui_tiao_screener',
                'shi_pan_xian_screener',
                'jin_feng_huang_screener',
                'yin_feng_huang_screener',
                'zhang_ting_bei_liang_yin_screener'
            )
            ORDER BY id
        ''')
        screener_types = cursor.fetchall()

        # Build results for each screener
        pool_screeners = []
        for screener in screener_types:
            screener_id = screener['id']
            screener_code = screener['code']

            # Get recent pool hits (last 20)
            cursor.execute('''
                SELECT r.code, s.name, r.signal_type, r.score, r.price,
                       r.position_size, r.action, r.screen_date
                FROM pool_screening_results r
                JOIN stocks s ON r.code = s.code
                WHERE r.screener_id = ?
                ORDER BY r.screen_date DESC, r.created_at DESC
                LIMIT 20
            ''', (screener_id,))
            recent_hits = [
                {
                    'code': row['code'],
                    'name': row['name'],
                    'signal_type': row['signal_type'],
                    'score': row['score'],
                    'price': row['price'],
                    'position_size': row['position_size'],
                    'action': row['action'],
                    'screen_date': row['screen_date']
                }
                for row in cursor.fetchall()
            ]

            # Get last run date
            cursor.execute('''
                SELECT MAX(screen_date) as last_run_date
                FROM pool_screening_results
                WHERE screener_id = ?
            ''', (screener_id,))
            last_run_row = cursor.fetchone()
            last_run_date = last_run_row['last_run_date'] if last_run_row['last_run_date'] else None

            # Get pool size from lao_ya_tou_pool table
            cursor.execute('SELECT COUNT(*) as count FROM lao_ya_tou_pool')
            pool_row = cursor.fetchone()
            pool_size = pool_row['count'] if pool_row else 0

            # Calculate summary stats
            pool_hits = len(recent_hits)
            summary = {
                'total_pool_stocks': pool_size,
                'processed': pool_hits,
                'errors': 0,
                'hits': pool_hits
            }

            pool_screeners.append({
                'screener_id': screener_id,
                'screener_code': screener_code,
                'display_name': screener['display_name'],
                'last_run_date': last_run_date,
                'pool_hits': pool_hits,
                'recent_hits': recent_hits,
                'summary': summary
            })

        conn.close()

        # Extract LYT specific data
        lyt_data = None
        for screener in pool_screeners:
            if screener['screener_code'] == 'lao_ya_tou_zhou_xian_screener':
                lyt_data = {
                    'last_run_date': screener['last_run_date'],
                    'pool_size': screener['summary']['total_pool_stocks'],
                    'signal_distribution': {
                        'signal_1': 0,  # Will be filled from pool query
                        'signal_2': 0,
                        'signal_3': 0
                    }
                }
                break

        # Get signal distribution for LYT
        if lyt_data and lyt_data.get('pool_size', 0) > 0:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT current_signal, COUNT(*) as count
                FROM lao_ya_tou_pool
                GROUP BY current_signal
            ''')
            for row in cursor.fetchall():
                signal = row['current_signal']
                if signal == 'signal_1':
                    lyt_data['signal_distribution']['signal_1'] = row['count']
                elif signal == 'signal_2':
                    lyt_data['signal_distribution']['signal_2'] = row['count']
                elif signal == 'signal_3':
                    lyt_data['signal_distribution']['signal_3'] = row['count']
            conn.close()

        return jsonify({
            'success': True,
            'data': {
                'lyt': lyt_data,
                'pool_screeners': pool_screeners
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/screeners/<name>', methods=['POST'])
@require_auth
def rollback_screener_config(name):
    """Rollback screener configuration to a specific version"""
    try:
        data = request.get_json()
        version = data.get('version')

        if not version:
            return jsonify({'error': 'Version is required'}), 400

        from models import rollback_screener_config

        # Rollback
        success, error = rollback_screener_config(name, version)
        if not success:
            return jsonify({'error': error}), 400

        return jsonify({
            'success': True,
            'message': f'Rollback to version {version} successful'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<name>/<date>', methods=['GET'])
@require_auth
def download_screener_file(name, date):
    """Download screener result file directly"""
    from flask import send_file
    from pathlib import Path

    # Use the already-defined _WORKSPACE_ROOT
    workspace_root = _WORKSPACE_ROOT

    # 尝试多个可能的路径
    possible_paths = []

    # 1. 标准路径: data/screeners/{name}/{date}.xlsx
    dir_name = name.replace('_screener', '')
    possible_paths.append(workspace_root / 'data' / 'screeners' / dir_name / f'{date}.xlsx')

    # 2. 旧路径: data/{name}_{date}.xlsx
    possible_paths.append(workspace_root / 'data' / f'{name}_{date}.xlsx')
    
    # 3. 每日热冷股路径
    if name == 'daily_hot_cold_screener':
        possible_paths.append(workspace_root / 'data' / '每日热冷股' / f'{date}.xlsx')
        possible_paths.append(workspace_root / 'data' / '每日热冷股' / f'{date}_hot.xlsx')
        possible_paths.append(workspace_root / 'data' / '每日热冷股' / f'{date}_cold.xlsx')
    
    # 查找存在的文件
    file_path = None
    for path in possible_paths:
        if path.exists():
            file_path = path
            break
    
    if not file_path:
        return jsonify({'error': 'File not found'}), 404
    
    try:
        return send_file(file_path, as_attachment=True, download_name=f'{name}_{date}.xlsx')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 检查单个股票是否符合筛选条件
@app.route('/api/check-stock', methods=['POST'])
@require_auth
def check_stock():
    """检查单个股票是否符合筛选条件"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    screener_name = data.get('screener')
    stock_code = data.get('code')
    date = data.get('date')

    print(f"[DEBUG] check_stock called with screener={screener_name}, code={stock_code}, date={date}")
    
    if not screener_name or not stock_code:
        return jsonify({'error': 'Screener name and stock code are required'}), 400
    
    # 标准化股票代码
    code = stock_code.strip()
    if '.' in code:
        # 如果是 sh.600000 格式，提取纯数字部分
        code = code.split('.')[-1]

    # Check if screener supports single stock check
    supported_screeners = [
        'coffee_cup_screener', 'coffee_cup_handle_screener_v4', 'double_bottom_screener', 'flat_base_screener',
        'high_tight_flag_screener', 'ascending_triangle_screener',
        'breakout_main_screener', 'shi_pan_xian_screener'
    ]

    if screener_name not in supported_screeners:
        print(f"[DEBUG] Screener {screener_name} not supported, returning early")
        return jsonify({
            'match': False,
            'code': code,
            'name': '',
            'date': date or '',
            'reasons': ['该筛选器暂不支持单个股票检查功能']
        })

    try:
        # 导入对应的筛选器
        import sys
        sys.path.insert(0, str(DASHBOARD_DIR.parent / 'screeners'))
        
        # 获取筛选器模块和类名
        # 只支持有 check_single_stock 方法的筛选器
        screeners_with_check_single = [
            'coffee_cup_handle_screener_v4', 'double_bottom_screener', 'flat_base_screener',
            'high_tight_flag_screener', 'ascending_triangle_screener',
            'breakout_main_screener', 'shi_pan_xian_screener',
            'lao_ya_tou_zhou_xian_screener'
        ]

        module_map = {
            'coffee_cup_handle_screener_v4': ('coffee_cup_handle_screener_v4', 'CoffeeCupHandleScreenerV4'),
            'double_bottom_screener': ('double_bottom_screener', 'DoubleBottomScreener'),
            'flat_base_screener': ('flat_base_screener', 'FlatBaseScreener'),
            'high_tight_flag_screener': ('high_tight_flag_screener', 'HighTightFlagScreener'),
            'ascending_triangle_screener': ('ascending_triangle_screener', 'AscendingTriangleScreener'),
            'breakout_main_screener': ('breakout_main_screener', 'BreakoutMainScreener'),
            'shi_pan_xian_screener': ('shi_pan_xian_screener', 'ShiPanXianScreener'),
            'lao_ya_tou_zhou_xian_screener': ('lao_ya_tou_zhou_xian_screener', 'LaoYaTouZhouXianScreenerV2'),
        }
        
        if screener_name not in module_map:
            print(f"[DEBUG] Screener {screener_name} not in supported list, returning error")
            return jsonify({
                'match': False,
                'code': code,
                'name': '',
                'date': date or '',
                'reasons': ['该筛选器暂不支持单个股票检查功能']
            })

        # Get module and class name from module_map
        module_name, class_name = module_map[screener_name]

        module = __import__(module_name)
        screener_class = getattr(module, class_name)
        
        # 实例化筛选器，使用正确的数据库路径
        db_path = str(_WORKSPACE_ROOT / 'data' / 'stock_data.db')
        if screener_name == 'coffee_cup_handle_screener_v4':
            screener = screener_class(db_path=db_path, enable_news=False, enable_llm=False, enable_progress=False)
        else:
            screener = screener_class(db_path=db_path)
        
        # 检查单个股票
        result = screener.check_single_stock(code, date)
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'match': False,
            'code': code,
            'name': '',
            'date': date or '',
            'reasons': [f'检查出错: {str(e)}']
        })


# ==================== Monitor API Endpoints ====================

@app.route('/api/monitor/screeners', methods=['GET'])
@require_auth
def list_monitor_screeners():
    """List all screeners with pick counts for monitor"""
    try:
        # Import the monitor
        sys.path.insert(0, str(DASHBOARD_DIR.parent / 'scripts'))
        from screener_monitor import ScreenerMonitor
        
        monitor = ScreenerMonitor()
        
        # Query distinct screener_ids directly from screener_picks table
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(str(_STOCK_DB))
        conn.row_factory = _sqlite3.Row
        rows = conn.execute(
            """SELECT screener_id, COUNT(*) as pick_count
               FROM screener_picks
               GROUP BY screener_id
               ORDER BY pick_count DESC"""
        ).fetchall()
        conn.close()
        
        result = []
        for i, row in enumerate(rows):
            sid = row['screener_id']
            result.append({
                'id': i + 1,
                'name': sid,
                'display_name': sid.replace('_screener', '').replace('_', ' ').title(),
                'pick_count': row['pick_count']
            })
        
        return jsonify({'screeners': result})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitor/pipeline', methods=['GET'])
@require_auth
def get_pipeline_data():
    """Get pipeline data for a specific screener"""
    screener_id = request.args.get('screener_id')
    
    if not screener_id:
        return jsonify({'error': 'screener_id is required'}), 400
    
    try:
        # Import the monitor
        sys.path.insert(0, str(DASHBOARD_DIR.parent / 'scripts'))
        from screener_monitor import ScreenerMonitor
        
        monitor = ScreenerMonitor()
        
        # Get all picks for this screener
        picks = monitor.get_picks_by_screener(screener_id, limit=1000)
        
        # Calculate stats
        stats = {
            'total': len(picks),
            'active': sum(1 for p in picks if p.status == 'active'),
            'graduated': sum(1 for p in picks if p.status == 'graduated'),
            'failed': sum(1 for p in picks if p.status == 'failed'),
            'win_rate': 0.0
        }
        
        # Calculate win rate
        completed = stats['graduated'] + stats['failed']
        if completed > 0:
            stats['win_rate'] = round(stats['graduated'] / completed * 100, 1)
        
        # Convert picks to dict format and fetch stock names
        picks_data = []
        for pick in picks:
            pick_dict = pick.to_dict()
            
            # Fetch stock info + today's pct_change from database
            try:
                price_db = str(_STOCK_DB)
                conn = __import__('sqlite3').connect(price_db)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, industry, total_market_cap, pe_ratio FROM stocks WHERE code = ?",
                    (pick.stock_code,)
                )
                row = cursor.fetchone()
                if row:
                    pick_dict['stock_name']  = row[0] or '-'
                    pick_dict['industry']    = row[1] or '-'
                    pick_dict['market_cap']  = row[2]
                    pick_dict['pe']          = row[3]
                else:
                    pick_dict['stock_name']  = '-'
                    pick_dict['industry']    = '-'
                    pick_dict['market_cap']  = None
                    pick_dict['pe']          = None
                cursor.execute(
                    "SELECT pct_change FROM daily_prices WHERE code = ? ORDER BY trade_date DESC LIMIT 1",
                    (pick.stock_code,)
                )
                pr = cursor.fetchone()
                pick_dict['pct_change'] = pr[0] if pr else None
                conn.close()
            except Exception as e:
                pick_dict['stock_name']  = '-'
                pick_dict['industry']    = '-'
                pick_dict['market_cap']  = None
                pick_dict['pe']          = None
                pick_dict['pct_change']  = None
                conn.close()
            except Exception as e:
                print(f"DEBUG: Error fetching stock name: {e}")
                pick_dict['stock_name'] = '-'
            
            picks_data.append(pick_dict)
        
        return jsonify({
            'screener_id': screener_id,
            'picks': picks_data,
            'stats': stats
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/strategy/backtests', methods=['GET'])
@require_auth
def get_strategy_backtests():
    """获取策略回测历史记录"""
    try:
        db_path = str(_STOCK_DB)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute('''
            SELECT
                id,
                strategy_version,
                total_return,
                sharpe_ratio,
                max_drawdown,
                win_rate,
                total_trades,
                profit_factor,
                created_at
            FROM strategy_backtest_results
            ORDER BY created_at ASC
        ''')

        backtests = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            'backtests': backtests,
            'count': len(backtests)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'backtests': [], 'count': 0}), 500


@app.route('/api/strategy/trades/<int:backtest_id>', methods=['GET'])
@require_auth
def get_strategy_trades(backtest_id):
    """获取指定回测的交易明细"""
    try:
        db_path = str(_STOCK_DB)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Get trades with stock names
        cursor = conn.execute('''
            SELECT 
                t.*,
                s.name as stock_name
            FROM strategy_trades t
            LEFT JOIN stocks s ON t.code = s.code
            WHERE t.backtest_id = ?
            ORDER BY t.trade_date ASC
        ''', (backtest_id,))

        trades = [dict(row) for row in cursor.fetchall()]

        # Calculate summary
        total_profit = sum(t['realized_pnl'] for t in trades if t['realized_pnl'] and t['realized_pnl'] > 0)
        total_loss = sum(t['realized_pnl'] for t in trades if t['realized_pnl'] and t['realized_pnl'] < 0)
        win_count = len([t for t in trades if t['realized_pnl'] and t['realized_pnl'] > 0])
        loss_count = len([t for t in trades if t['realized_pnl'] and t['realized_pnl'] <= 0])

        conn.close()

        return jsonify({
            'trades': trades,
            'summary': {
                'total_trades': len(trades),
                'win_count': win_count,
                'loss_count': loss_count,
                'total_profit': total_profit,
                'total_loss': total_loss,
                'net_pnl': total_profit + total_loss,
                'avg_hold_days': sum(t['hold_days'] or 0 for t in trades) / len(trades) if trades else 0
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'trades': [], 'summary': {}}), 500


@app.route('/api/stats/access', methods=['GET'])
@require_auth
def get_access_statistics():
    """获取访问统计（今日和本月）"""
    try:
        stats = get_access_stats()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 数据健康 API ====================

_STATUS_FILE    = _WORKSPACE_ROOT / 'logs' / 'last_run_status.json'
_RUN_HISTORY_FILE = _WORKSPACE_ROOT / 'logs' / 'run_history.json'
_SCRIPTS_DIR    = _WORKSPACE_ROOT / 'scripts'
_STOCK_DB       = _WORKSPACE_ROOT / 'data' / 'stock_data.db'


@app.route('/api/data-health', methods=['GET'])
@require_auth
def get_data_health():
    result = {}

    try:
        result['last_run'] = json.loads(_STATUS_FILE.read_text(encoding='utf-8')) if _STATUS_FILE.exists() else None
    except Exception as e:
        result['last_run'] = {'error': str(e)}

    try:
        if _RUN_HISTORY_FILE.exists():
            history = json.loads(_RUN_HISTORY_FILE.read_text(encoding='utf-8'))
            result['run_history'] = list(reversed(history[-20:]))
        else:
            result['run_history'] = []
    except Exception:
        result['run_history'] = []

    try:
      sys.path.insert(0, str(_SCRIPTS_DIR))
      from data_health_check import DataHealthChecker
      checker = DataHealthChecker(db_path=str(_STOCK_DB))
      result['db_health'] = checker.run_all_checks()

    except Exception as e:
          result['db_health'] = {'status': 'error', 'error': str(e), 'checks': {}}

    try:
          date_key = (result.get('last_run') or {}).get('date') or __import__('datetime').date.today().isoformat()
          rp = _WORKSPACE_ROOT / 'logs' / f'orchestrator_report_{date_key}.json'
          result['step_report'] = json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else None

    except Exception:
        result['step_report'] = None

    return safe_jsonify(result)



_download_lock = __import__('threading').Lock()
_download_running = False

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
    logger.info(f"Upload request: filename={file.filename}, force_update={force_update}")

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
                'warnings': result['errors'] if result['errors'] else None
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


@app.route('/api/data-health/run', methods=['POST'])
def trigger_data_download():
    import subprocess
    import threading
    global _download_running

    orchestrator = _SCRIPTS_DIR / 'download_orchestrator.py'
    if not orchestrator.exists():
        return jsonify({'success': False, 'error': 'download_orchestrator.py not found'}), 404

    with _download_lock:
        if _download_running:
            return jsonify({'success': False, 'message': '下载任务正在运行中，请稍后再试'}), 429
        _download_running = True

    def _bg():
        global _download_running
        try:
            env = __import__('os').environ.copy()
            env['OPENCLAW_WORKSPACE'] = str(_WORKSPACE_ROOT)
            subprocess.run(
                [sys.executable, str(orchestrator), "--no-backfill"],
                cwd=str(_WORKSPACE_ROOT),
                env=env,
                timeout=3600
            )
        except Exception:
            pass
        finally:
            with _download_lock:
                _download_running = False

    threading.Thread(target=_bg, daemon=True).start()
    return jsonify({'success': True, 'message': '数据下载已在后台启动，请稍后刷新查看状态'})


# Register strategy blueprint
app.register_blueprint(strategy_bp)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765, help='Port to run on')
    args = parser.parse_args()
    
    print("Starting Trading Screener Dashboard API...")
    print(f"Database: {DASHBOARD_DIR.parent / 'data' / 'dashboard.db'}")
    print(f"Port: {args.port}")
    print(f"Multi-threading enabled for concurrent users")
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)
