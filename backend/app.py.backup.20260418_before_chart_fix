#!/usr/bin/env python3
"""
Flask Backend API for Trading Screener Dashboard
"""
import os
import sys
import json
import math
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


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 8765))
    print(f'[DEBUG] Starting Flask server on port {port}...')
    app.run(host='0.0.0.0', port=port, debug=False)
