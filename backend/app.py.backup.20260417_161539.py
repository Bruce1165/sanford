#!/usr/bin/env python3
"""
Flask Backend API for Trading Screener Dashboard
"""
import os
import sys
import json
import math
from pathlib import Path
from datetime import datetime, date
from functools import wraps

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
    init_db, get_db_connection, get_stock_db_connection, get_all_screeners, get_screener,
    get_runs, get_run, get_results, get_results_by_date,
    log_access, get_access_stats
)

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


# Authentication
DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')
if not DASHBOARD_PASSWORD:
    raise ValueError("DASHBOARD_PASSWORD environment variable is required")


def check_auth(username, password):
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
    return send_from_directory(
        DASHBOARD_DIR.parent / 'frontend/dist/assets', filename
    )


@app.route('/<path:path>')
def catch_all(path):
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

    if screener_name:
        results = get_results_by_date(screener_name, run_date)
    else:
        results = get_results_by_date(run_date)

    return safe_jsonify(results)


@app.route('/api/screeners/<screener_name>/run', methods=['POST'])
def run_screener(screener_name):
    """Run a screener"""
    try:
        # Get run_date from request body
        request_data = request.get_json() or {}
        run_date = request_data.get('date')

        if not run_date:
            return jsonify({'error': 'Missing date parameter'}), 400

        # Validate date format
        try:
            datetime.strptime(run_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

        # Call the actual screener run function
        run_id = run_screener_subprocess(screener_name, run_date)

        return jsonify({
            'status': 'success',
            'screener': screener_name,
            'run_id': run_id,
            'date': run_date
        })

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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

    # Build parameters with schema metadata
    for param_name, param_config in schema.items():
        param_data = param_config.copy()
        # Override value with current config value if exists
        if param_name in config.get('parameters', {}):
            param_data['value'] = config['parameters'][param_name].get('value', param_config.get('default'))
        else:
            param_data['value'] = param_config.get('default')
        merged_config['parameters'][param_name] = param_data

    return safe_jsonify(merged_config)


@app.route('/api/screeners/<screener_name>/config', methods=['PUT'])
def update_screener_config(screener_name):
    """Update screener configuration"""
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400
    
    config_data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get existing config
    cursor.execute(
        'SELECT display_name, description, category, config_json, config_schema '
        'FROM screener_configs WHERE screener_name = ?',
        (screener_name,)
    )
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Screener not found'}), 404
    
    display_name, description, category, config_json, schema_json = row
    schema = json.loads(schema_json)
    existing_config = json.loads(config_json) if config_json else {'parameters': {}}
    
    # Merge new config with existing parameters
    merged_config = {
        'display_name': display_name,
        'description': description,
        'category': category,
        'parameters': existing_config.get('parameters', {}).copy()
    }
    
    # Update parameters from request
    if 'parameters' in config_data:
        for param_name, param_value in config_data['parameters'].items():
            if schema and param_name in schema:
                # Use schema for validation if available
                merged_config['parameters'][param_name] = {
                    'value': param_value,
                    'display_name': schema[param_name].get('display_name', param_name),
                    'description': schema[param_name].get('description', ''),
                    'group': schema[param_name].get('group', '其他'),
                    'type': schema[param_name].get('type', 'string'),
                    'min': schema[param_name].get('min'),
                    'max': schema[param_name].get('max'),
                    'step': schema[param_name].get('step'),
                    'default': schema[param_name].get('default')
                }
            else:
                # If schema is empty or param not found, preserve full param structure from request
                merged_config['parameters'][param_name] = param_value
    
    # Save to database
    config_json = json.dumps(merged_config)
    cursor.execute(
        'UPDATE screener_configs SET config_json = ?, current_version = ? '
        'WHERE screener_name = ?',
        (config_json, 'v1.0', screener_name)
    )
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'config': merged_config})
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


@app.route('/api/data-health')
def data_health():
    """Get data health status"""
    # Check stock data database
    stock_db_path = DASHBOARD_DIR.parent / 'data' / 'stock_data.db'
    stock_db_exists = stock_db_path.exists()

    # Get last data date
    last_date = None
    if stock_db_exists:
        conn = get_stock_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT MAX(trade_date) FROM daily_prices '
            'WHERE trade_date < ?',
            (date.today(),)
        )
        row = cursor.fetchone()
        if row and row[0]:
            last_date = row[0]
        conn.close()

    return jsonify({
        'stock_data_db': 'ok' if stock_db_exists else 'missing',
        'last_data_date': last_date,
        'dashboard_db': 'ok'
    })


# Initialize database
print('[DEBUG] Initializing database...')
init_db()
print('[DEBUG] Registering screeners...')
register_discovered_screeners()

# Load screener configurations from config/screeners/*.json
print('[DEBUG] Loading screener configurations...')
config_dir = DASHBOARD_DIR.parent / 'config' / 'screeners'
if config_dir.exists():
    import glob
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


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 8765))
    print(f'[DEBUG] Starting Flask server on port {port}...')
    app.run(host='0.0.0.0', port=port, debug=False)
