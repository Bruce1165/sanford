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
from pathlib import Path
from datetime import datetime, date, timedelta
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

# Import excel upload handler
from excel_upload import handle_excel_upload

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

    # Load fallback schema from JSON config file if database schema is empty
    if not schema:
        config_file_path = DASHBOARD_DIR.parent / 'config' / 'screeners' / f'{screener_name}.json'
        if config_file_path.exists():
            try:
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # Use parameters from file as schema
                    schema = file_config.get('parameters', {})
                    print(f"[DEBUG] Loaded schema from config file: {len(schema)} parameters")
            except Exception as e:
                print(f"[DEBUG] Failed to load config file: {e}")

    # Build parameters with schema metadata (fallback to config if schema is empty)
    if schema:
        for param_name, param_config in schema.items():
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

    cursor.execute('SELECT COUNT(*) FROM stocks WHERE sector_lv1 IS NOT NULL AND sector_lv1 != ""')
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
        (screener_name, display_name, category) = row
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
        (stock_code, stock_name, close_price, turnover, pct_change, extra_data, started_at) = row

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


@app.route('/api/five-flags/pools', methods=['GET'])
def five_flags_pools():
    """List LaoYaTou pools with filters and pagination"""
    try:
        processed = (request.args.get('processed') or 'all').lower()
        stock_code = request.args.get('stock_code')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = _safe_int_arg('limit', 50, min_value=1, max_value=500)
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

        count_sql = f'SELECT COUNT(*) AS total FROM lao_ya_tou_five_flags {where_sql}'
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        list_sql = f'''
            SELECT id, pool_id, screener_id, stock_code, stock_name, screen_date,
                   close_price, match_reason, extra_data, created_at
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
            items.append(record)

        return safe_jsonify({
            'items': items,
            'total': total,
            'limit': limit,
            'offset': offset,
            'dedupe_key': ['stock_code', 'screener_id', 'screen_date']
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
            SELECT screen_date, screener_id, match_reason, close_price, pool_id, created_at
            FROM lao_ya_tou_five_flags
            WHERE {where_sql}
            ORDER BY screen_date ASC, screener_id ASC
            ''',
            params
        )
        rows = cursor.fetchall()
        conn.close()

        timeline_map = {}
        for row in rows:
            d = row['screen_date']
            if d not in timeline_map:
                timeline_map[d] = {
                    'date': d,
                    'hits': [],
                    'details': []
                }
            timeline_map[d]['hits'].append(row['screener_id'])
            timeline_map[d]['details'].append({
                'screener_id': row['screener_id'],
                'match_reason': row['match_reason'],
                'close_price': row['close_price'],
                'pool_id': row['pool_id'],
                'created_at': row['created_at']
            })

        timeline = [timeline_map[k] for k in sorted(timeline_map.keys())]
        return safe_jsonify({'stock_code': stock_code, 'timeline': timeline})
    except Exception as e:
        return jsonify({'error': f'failed to query timeline: {str(e)}'}), 500


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
    for run in runs:
        status = run.get('status')
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


def _start_five_flags_run(pool_ids=None, max_workers=None, dry_run=False, retry_of=None, snapshot_id=None):
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
            'dry_run': True
        }

    cmd = [sys.executable, str(script_path)]
    if max_workers is not None:
        cmd.extend(['--max-workers', str(max_workers)])
    if pool_ids:
        cmd.extend(['--pool-ids', ','.join(str(x) for x in pool_ids)])

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


@app.route('/api/five-flags/run', methods=['POST'])
def five_flags_run():
    """Start five-flags screening task asynchronously"""
    try:
        payload = request.get_json(silent=True) or {}
        pool_ids = payload.get('pool_ids') or []
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

        # Guard: allow only one active run to avoid dashboard resource contention
        runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
        active = next((r for r in runs if r.get('status') in ('running', 'accepted')), None)
        if active and _is_pid_running(active.get('pid')):
            return jsonify({
                'error': 'five-flags run already in progress',
                'active_run_id': active.get('run_id')
            }), 409

        result = _start_five_flags_run(
            pool_ids=normalized_pool_ids,
            max_workers=max_workers,
            dry_run=dry_run,
            snapshot_id=payload.get('snapshot_id')
        )
        return safe_jsonify(result), 202
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'failed to start five-flags run: {str(e)}'}), 500


@app.route('/api/five-flags/retry-failed', methods=['POST'])
def five_flags_retry_failed():
    """Retry failed pool items by explicit pool_ids (safe wrapper over /run)"""
    try:
        payload = request.get_json(silent=True) or {}
        pool_ids = payload.get('pool_ids') or []
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

        runs = _refresh_five_flags_run_registry(_load_five_flags_runs_registry())
        active = next((r for r in runs if r.get('status') in ('running', 'accepted')), None)
        if active and _is_pid_running(active.get('pid')):
            return jsonify({
                'error': 'five-flags run already in progress',
                'active_run_id': active.get('run_id')
            }), 409

        result = _start_five_flags_run(
            pool_ids=normalized_pool_ids,
            max_workers=max_workers,
            dry_run=False,
            retry_of=payload.get('run_id')
        )
        return safe_jsonify({
            'retry_run_id': result.get('run_id'),
            'status': result.get('status'),
            'retry_count': len(normalized_pool_ids)
        }), 202
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'failed to retry failed pools: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 8765))
    print(f'[DEBUG] Starting Flask server on port {port}...')
    app.run(host='0.0.0.0', port=port, debug=False)
