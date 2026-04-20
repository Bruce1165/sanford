#!/bin/bash
# 卸载 Flask 服务

set -e

LAUNCHD_DIR="$HOME/Library/LaunchAgents"
SERVICE_NAME="com.neotrade2.flask"

echo "=========================================="
echo "NeoTrade2 Flask 服务卸载"
echo "=========================================="

# 检查服务是否存在
if ! launchctl list | grep -q "$SERVICE_NAME"; then
    echo "服务未安装或未运行"
    exit 0
fi

# 停止服务
echo "停止服务..."
launchctl stop "$SERVICE_NAME" 2>/dev/null || true

# 卸载服务
echo "卸载服务..."
launchctl unload "$LAUNCHD_DIR/$SERVICE_NAME.plist" 2>/dev/null || true

# 删除 plist 文件
echo "删除配置文件..."
rm -f "$LAUNCHD_DIR/$SERVICE_NAME.plist"

# 手动停止可能残留的进程
echo "清理残留进程..."
pkill -f "python3.*app.py" 2>/dev/null || true

echo ""
echo "✓ 服务卸载完成"
echo ""
echo "如需重新安装，运行:"
echo "  bash $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install_flask_service.sh"
