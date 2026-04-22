"""
app.py – Flask Dashboard

展示预测结果和模型性能。
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('DASHBOARD_SECRET', 'dev-secret-key')

DB_PATH = Path(__file__).parent.parent / 'data' / 'predictions.db'


def get_predictions(date_str=None, limit=100):
    """获取预测结果"""
    with sqlite3.connect(str(DB_PATH)) as conn:
        if date_str:
            query = """
                SELECT * FROM predictions
                WHERE prediction_date = ?
                ORDER BY rank ASC
                LIMIT ?
            """
            params = (date_str, limit)
        else:
            query = """
                SELECT * FROM predictions
                ORDER BY prediction_date DESC, rank ASC
                LIMIT ?
            """
            params = (limit,)

        return conn.execute(query, params).fetchall()


def get_latest_date():
    """获取最新预测日期"""
    with sqlite3.connect(str(DB_PATH)) as conn:
        row = conn.execute("SELECT MAX(prediction_date) FROM predictions").fetchone()
        return row[0] if row and row[0] else None


def get_model_performance():
    """获取模型性能"""
    with sqlite3.connect(str(DB_PATH)) as conn:
        rows = conn.execute("""
            SELECT * FROM model_performance
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()
    return rows


@app.route('/')
def index():
    """首页 - 最新预测"""
    latest_date = get_latest_date()

    if latest_date:
        predictions = get_predictions(latest_date, limit=50)
        model_perf = get_model_performance()
    else:
        predictions = []
        model_perf = []

    return render_template(
        'index.html',
        predictions=predictions,
        latest_date=latest_date,
        model_perf=model_perf
    )


@app.route('/api/predictions')
def api_predictions():
    """API: 获取预测结果"""
    date_str = request.args.get('date')
    limit = int(request.args.get('limit', 100))

    predictions = get_predictions(date_str, limit)

    return jsonify({
        'date': date_str or 'latest',
        'count': len(predictions),
        'data': [
            {
                'code': p[0],
                'name': p[1],
                'probability': p[2],
                'rank': p[4]
            }
            for p in predictions
        ]
    })


@app.route('/api/performance')
def api_performance():
    """API: 获取模型性能"""
    perf = get_model_performance()

    return jsonify({
        'count': len(perf),
        'data': [
            {
                'model_name': p[0],
                'version': p[1],
                'precision': p[4],
                'recall': p[5],
                'f1': p[6],
                'auc': p[7],
                'created_at': p[13]
            }
            for p in perf
        ]
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
