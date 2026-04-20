# 健康检查函数手动替换指南

## 问题
当前 health_check 函数在 /api/health 端点中调用 DataHealthChecker，某些检查失败时会返回 500 错误。

## 手动替换步骤

### 步骤 1：备份当前 app.py
```bash
cp backend/app.py backend/app.py.manual_backup_$(date +%Y%m%d_%H%M%S)
```

### 步骤 2：在 app.py 中替换 health_check 函数

需要替换的内容位置：
- 从第 109 行附近开始（导入 sys.path.insert）
- 到第 1115 行附近（except Exception as e: 结束）

替换为以下内容：

```python
@app.route('/api/health', methods=['GET'])
def health_check():
    \"\"\"改进版本的健康检查端点\"\"\"
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
        statuses = [c['status'] for c in result['checks']].values()]
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
```

### 步骤 3：验证并重启 Flask

```bash
# 检查语法
python3 -m py_compile backend/app.py

# 如果没有错误，重启 Flask
pkill -f "backend/app.py:app"
python3 backend/app.py
```

### 步骤 4：清理临时文件
```bash
rm backend/app.py.manual_backup_$(date +%Y%m%d_%H%M%S)
```

---

**注意：** 替换后请检查 Dashboard 是否可以正常加载。如果正常，说明改进成功。
