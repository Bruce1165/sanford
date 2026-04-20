#!/bin/bash
# 安装 Flask 服务到 Launchd

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$SCRIPT_DIR/com.neotrade2.flask.plist"
SERVICE_NAME="com.neotrade2.flask"

echo "=========================================="
echo "NeoTrade2 Flask 服务安装"
echo "=========================================="

# 确保日志目录存在
mkdir -p "$PROJECT_ROOT/logs"

# 停止并卸载旧服务（如果存在）
if launchctl list | grep -q "$SERVICE_NAME"; then
    echo "发现已存在的服务，正在停止..."
    launchctl unload "$LAUNCHD_DIR/$SERVICE_NAME.plist" 2>/dev/null || true
    sleep 1
fi

# 复制 plist 文件到 LaunchAgents
echo "安装服务配置..."
cp "$PLIST_FILE" "$LAUNCHD_DIR/$SERVICE_NAME.plist"

# 加载并启动服务
echo "启动服务..."
launchctl load "$LAUNCHD_DIR/$SERVICE_NAME.plist"
launchctl start "$SERVICE_NAME"

# 等待服务启动
sleep 2

# 检查服务状态
if launchctl list | grep -q "$SERVICE_NAME"; then
    echo ""
    echo "✓ 服务安装成功并已启动"
    echo ""
    echo "服务名称: $SERVICE_NAME"
    echo "日志路径:"
    echo "  标准输出: $PROJECT_ROOT/logs/flask.stdout.log"
    echo "  错误输出: $PROJECT_ROOT/logs/flask.stderr.log"
    echo ""
    echo "管理命令:"
    echo "  查看状态: launchctl list | grep $SERVICE_NAME"
    echo "  停止服务: launchctl stop $SERVICE_NAME"
    echo "  启动服务: launchctl start $SERVICE_NAME"
    echo "  卸载服务: bash $SCRIPT_DIR/uninstall_flask_service.sh"
    echo ""
    echo "Dashboard: http://localhost:8765"
else
    echo ""
    echo "✗ 服务启动失败，请查看日志:"
    echo "  tail -f $PROJECT_ROOT/logs/flask.stderr.log"
    exit 1
fi
