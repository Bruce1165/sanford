#!/bin/bash
# quick_start.sh – 快速启动脚本

echo "=== STOCKPREDICTION 快速启动 ==="

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
else
    echo "激活虚拟环境..."
    source venv/bin/activate
fi

# 检查依赖
echo "检查依赖..."
pip install -q pandas numpy scikit-learn xgboost sqlalchemy

# 初始化数据库
echo "初始化数据库..."
python -c "
from models.database import init_db, LABELS_DB, FEATURES_DB, SCREENER_SCORES_DB, PREDICTIONS_DB
init_db(LABELS_DB)
init_db(FEATURES_DB)
init_db(SCREENER_SCORES_DB)
init_db(PREDICTIONS_DB)
print('数据库初始化完成')
"

echo ""
echo "=== 启动完成 ==="
echo ""
echo "下一步操作："
echo "1. 生成标签: python scripts/backtest_labels.py --start-date 2024-09-01 --end-date 2026-03-31"
echo "2. 计算特征: python scripts/compute_features.py --start-date 2024-09-01 --end-date 2026-03-31"
echo "3. 收集筛选器: python scripts/collect_screener_scores.py --start-date 2024-09-01 --end-date 2026-03-31"
echo "4. 训练模型: python scripts/train_model.py"
echo "5. 启动预测: python scripts/predict.py"
echo "6. 启动Dashboard: python dashboard/app.py"
