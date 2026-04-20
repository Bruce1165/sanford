#!/usr/bin/env python3
"""
Health Check Endpoint Improvement

改进版本的健康检查 API，提供：
1. 更好的错误处理和友好的错误消息
2. 区分 critical/warning/ok 状态
3. 不因为个别检查失败就返回 500
"""

import sys
import logging
from datetime import datetime

# Add to path
sys.path.insert(0, '/Users/mac/NeoTrade2/backend')

logger = logging.getLogger(__name__)


@app.route('/api/health', methods=['GET'])
def health_check_v2():
    """改进的健康检查端点"""
    try:
        import logging
        logger = logging.getLogger(__name__)

        # Get data_date parameter
        data_date = request.args.get('date')

        if not data_date:
            data_date = None

        # Import DataHealthChecker
        sys.path.insert(0, str(_SCRIPTS_DIR))
        from data_health_check import DataHealthChecker

        # Run health check with better error handling
        db_path = str(_WORKSPACE_ROOT / 'data' / 'stock_data.db')
        checker = DataHealthChecker(db_path=db_path)
        result = checker.run_all_checks()

        # Check overall status
        statuses = [c['status'] for c in result['checks'].values()]
        if 'critical' in statuses or 'error' in statuses:
            return jsonify({
                'status': 'error',
                'message': '部分健康检查失败，请查看日志',
                'checks': result['checks'],
                'timestamp': result['timestamp']
            })
        elif 'warning' in statuses:
            return jsonify({
                'status': 'warning',
                'message': '部分健康检查有警告，建议查看',
                'checks': result['checks'],
                'timestamp': result['timestamp']
            })
        else:
            return jsonify({
                'status': 'ok',
                'message': '系统健康',
                'checks': result['checks'],
                'timestamp': result['timestamp']
            })
    except Exception as e:
        logger.error(f'Health check failed: {e}')
        return jsonify({
            'status': 'error',
            'message': f'健康检查异常: {str(e)}',
            'timestamp': datetime.now().isoformat()
        })
