#!/usr/bin/env python3
"""
Strategy Management - 战法管理API蓝图
"""
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, date
from flask import Blueprint, jsonify, request

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

try:
    from models import (
        get_all_strategies, get_strategy, register_strategy, delete_strategy,
        update_strategy, create_strategy_run, complete_strategy_run,
        get_strategy_run, get_strategy_runs, save_strategy_signal,
        get_strategy_signals, get_strategy_signals_by_date, save_strategy_performance,
        get_strategy_performance
    )
    from strategies.strategy_factory import StrategyFactory
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# Create blueprint
strategy_bp = Blueprint('strategies', __name__)

# Set up logging
logger = logging.getLogger(__name__)


@strategy_bp.route('/api/strategies', methods=['GET'])
def list_strategies():
    """列出所有战法"""
    try:
        strategies = get_all_strategies()
        return jsonify({
            'success': True,
            'count': len(strategies),
            'strategies': strategies
        })
    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/api/strategies/<name>', methods=['GET'])
def get_strategy_detail(name):
    """获取战法详情"""
    try:
        strategy = get_strategy(name)
        if not strategy:
            return jsonify({
                'success': False,
                'error': f'Strategy not found: {name}'
            }), 404

        return jsonify({
            'success': True,
            'strategy': strategy
        })
    except Exception as e:
        logger.error(f"Error getting strategy {name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/api/strategies/<name>/run', methods=['POST'])
def run_strategy(name):
    """运行战法"""
    try:
        # Get request data
        data = request.get_json() or {}
        run_date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        config = data.get('config', {})

        # Validate date format
        try:
            date.fromisoformat(run_date)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid date format: {run_date}. Use YYYY-MM-DD'
            }), 400

        # Check if strategy exists
        strategy = get_strategy(name)
        if not strategy:
            return jsonify({
                'success': False,
                'error': f'Strategy not found: {name}'
            }), 404

        # Create strategy run record
        run_id = create_strategy_run(name, run_date, config)

        # Create strategy instance
        strategy_instance = StrategyFactory.create_strategy(name, strategy.get('config_json', {}))
        if not strategy_instance:
            complete_strategy_run(run_id, error_message=f"Failed to create strategy instance")
            return jsonify({
                'success': False,
                'error': f'Failed to create strategy instance: {name}'
            }), 500

        # Set analysis date
        strategy_instance.set_date(date.fromisoformat(run_date))

        # Get all stocks to analyze
        # TODO: Implement stock fetching logic similar to screeners
        stocks_analyzed = 0
        signals_found = 0
        signals = []

        try:
            # Import database for stock data
            import sqlite3 as _sqlite3
            stock_db_path = WORKSPACE_ROOT / "data" / "stock_data.db"
            conn = _sqlite3.connect(stock_db_path)
            conn.row_factory = _sqlite3.Row
            cursor = conn.cursor()

            # Get all active stocks
            cursor.execute('''
                SELECT code, name FROM stocks
                WHERE is_delisted = 0
                ORDER BY code
            ''')

            stocks = cursor.fetchall()
            stocks_analyzed = len(stocks)

            # Analyze each stock
            for stock in stocks:
                code = stock['code']
                stock_name = stock['name']

                try:
                    signal = strategy_instance.analyze_stock(code, stock_name)
                    if signal:
                        signals_found += 1
                        signals.append(signal)

                        # Save signal to database
                        save_strategy_signal(
                            run_id=run_id,
                            stock_code=code,
                            stock_name=stock_name,
                            signal_type=signal.get('signal', 'WATCH'),
                            signal_strength=signal.get('strength'),
                            signal_reason=signal.get('reason'),
                            entry_price=signal.get('entry_price'),
                            stop_loss=signal.get('stop_loss'),
                            take_profit=signal.get('take_profit'),
                            risk_reward_ratio=signal.get('risk_reward_ratio'),
                            confidence_score=signal.get('confidence'),
                            extra_data=signal.get('extra')
                        )

                except Exception as e:
                    logger.warning(f"Error analyzing stock {code}: {e}")
                    continue

            conn.close()

            # Calculate and save performance statistics
            if signals:
                total_strength = sum(s.get('strength', 0) for s in signals)
                total_confidence = sum(s.get('confidence', 0) for s in signals)
                buy_count = sum(1 for s in signals if s.get('signal') == 'BUY')
                sell_count = sum(1 for s in signals if s.get('signal') == 'SELL')
                watch_count = sum(1 for s in signals if s.get('signal') == 'WATCH')

                save_strategy_performance(
                    strategy_name=name,
                    run_id=run_id,
                    total_signals=signals_found,
                    buy_signals=buy_count,
                    sell_signals=sell_count,
                    watch_signals=watch_count,
                    avg_signal_strength=total_strength / signals_found if signals_found > 0 else 0,
                    avg_confidence=total_confidence / signals_found if signals_found > 0 else 0,
                    top_stocks=[{'code': s.get('stock_code'), 'strength': s.get('strength')} for s in signals[:10]]
                )

            # Mark run as completed
            complete_strategy_run(run_id, stocks_analyzed=stocks_analyzed, signals_found=signals_found)

            return jsonify({
                'success': True,
                'run_id': run_id,
                'strategy_name': name,
                'run_date': run_date,
                'stocks_analyzed': stocks_analyzed,
                'signals_found': signals_found,
                'signals': signals
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            complete_strategy_run(run_id, error_message=error_msg)
            raise

    except Exception as e:
        logger.error(f"Error running strategy {name}: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@strategy_bp.route('/api/strategies/<name>/runs', methods=['GET'])
def get_strategy_runs_list(name):
    """获取战法的历史运行记录"""
    try:
        limit = request.args.get('limit', 50, type=int)
        runs = get_strategy_runs(name, limit)

        return jsonify({
            'success': True,
            'strategy_name': name,
            'count': len(runs),
            'runs': runs
        })
    except Exception as e:
        logger.error(f"Error getting runs for strategy {name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/api/strategies/<name>/signals', methods=['GET'])
def get_strategy_signals_endpoint(name):
    """获取战法的信号结果"""
    try:
        run_date = request.args.get('date')

        if not run_date:
            return jsonify({
                'success': False,
                'error': 'Missing required parameter: date (YYYY-MM-DD)'
            }), 400

        # Validate date format
        try:
            date.fromisoformat(run_date)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid date format: {run_date}. Use YYYY-MM-DD'
            }), 400

        signals = get_strategy_signals_by_date(name, run_date)
        run = get_strategy_run(name, run_date)

        if not run:
            return jsonify({
                'success': False,
                'error': f'No run found for strategy {name} on {run_date}'
            }), 404

        return jsonify({
            'success': True,
            'strategy_name': name,
            'run_date': run_date,
            'run_id': run['id'],
            'signals_count': len(signals) if signals else 0,
            'signals': signals or []
        })
    except Exception as e:
        logger.error(f"Error getting signals for strategy {name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/api/strategies/<name>/performance', methods=['GET'])
def get_strategy_performance_endpoint(name):
    """获取战法的性能统计"""
    try:
        run_date = request.args.get('date')

        if not run_date:
            return jsonify({
                'success': False,
                'error': 'Missing required parameter: date (YYYY-MM-DD)'
            }), 400

        performance = get_strategy_performance(name, run_date)

        if not performance:
            return jsonify({
                'success': False,
                'error': f'No performance data found for strategy {name} on {run_date}'
            }), 404

        return jsonify({
            'success': True,
            'strategy_name': name,
            'run_date': run_date,
            'performance': performance
        })
    except Exception as e:
        logger.error(f"Error getting performance for strategy {name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/api/strategies', methods=['POST'])
def create_strategy():
    """创建新战法"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request body'
            }), 400

        # Validate required fields
        required_fields = ['name', 'display_name', 'category']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        # Register strategy in database
        register_strategy(
            name=data['name'],
            display_name=data['display_name'],
            description=data.get('description', ''),
            category=data['category'],
            file_path=data.get('file_path', ''),
            config=data.get('config', {}),
            version=data.get('version', 'v1.0.0')
        )

        return jsonify({
            'success': True,
            'message': f'Strategy {data["name"]} created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/api/strategies/<name>', methods=['PUT'])
def update_strategy_endpoint(name):
    """更新战法"""
    try:
        data = request.get_json() or {}

        # Check if strategy exists
        strategy = get_strategy(name)
        if not strategy:
            return jsonify({
                'success': False,
                'error': f'Strategy not found: {name}'
            }), 404

        # Update strategy
        update_strategy(
            name=name,
            display_name=data.get('display_name'),
            description=data.get('description'),
            category=data.get('category'),
            config=data.get('config'),
            is_active=data.get('is_active')
        )

        return jsonify({
            'success': True,
            'message': f'Strategy {name} updated successfully'
        })
    except Exception as e:
        logger.error(f"Error updating strategy {name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/api/strategies/<name>', methods=['DELETE'])
def delete_strategy_endpoint(name):
    """删除战法"""
    try:
        # Check if strategy exists
        strategy = get_strategy(name)
        if not strategy:
            return jsonify({
                'success': False,
                'error': f'Strategy not found: {name}'
            }), 404

        # Delete strategy
        delete_strategy(name)

        return jsonify({
            'success': True,
            'message': f'Strategy {name} deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting strategy {name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/api/strategies/sync', methods=['POST'])
def sync_strategies():
    """同步战法到数据库（发现并注册）"""
    try:
        StrategyFactory.sync_strategies_with_db(str(WORKSPACE_ROOT), sys.modules['models'])

        return jsonify({
            'success': True,
            'message': 'Strategies synced successfully'
        })
    except Exception as e:
        logger.error(f"Error syncing strategies: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Test endpoints
    print("Strategy Management API Blueprint")
    print("Available endpoints:")
    for rule in strategy_bp.url_map.iter_rules():
        print(f"  {rule.methods} {rule.rule}")
