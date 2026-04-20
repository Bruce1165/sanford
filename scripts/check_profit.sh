#!/bin/bash
# Strategy Profitability Monitor - 策略盈利监控
# 当 Autoresearch 产生盈利策略时发送通知

WORKSPACE="/Users/mac/NeoTrade2"
LOG_FILE="$WORKSPACE/logs/autoresearch.log"
RESULT_FILE="$WORKSPACE/backtest_result.json"
NOTIFY_FILE="/tmp/strategy_profit_notify.txt"

# 检查是否已经通知过
if [ -f "$NOTIFY_FILE" ]; then
    exit 0
fi

# 检查是否有结果文件
if [ ! -f "$RESULT_FILE" ]; then
    exit 0
fi

# 读取最新结果
SHARPE=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d.get('sharpe_ratio', -999))" 2>/dev/null)
RETURN=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d.get('total_return', -999))" 2>/dev/null)

# 检查是否盈利
if (( $(echo "$SHARPE > 0" | bc -l) )) || (( $(echo "$RETURN > 0" | bc -l) )); then
    echo "$(date): 🎉 策略已实现盈利！" >> "$NOTIFY_FILE"
    echo "夏普比率: $SHARPE" >> "$NOTIFY_FILE"
    echo "总收益率: $RETURN" >> "$NOTIFY_FILE"
    
    # 这里可以添加更多通知方式（如发送消息到用户）
    echo "通知: 策略已盈利 - Sharpe=$SHARPE, Return=$RETURN"
fi
