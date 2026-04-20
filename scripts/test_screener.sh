#!/bin/bash
# 快速测试单个筛选器
# 用法: bash scripts/test_screener.sh <筛选器名称> [显示名称]

set -e

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示帮助
if [ "$1" == "--help" ] || [ "$1" == "-h" ] || [ -z "$1" ]; then
    echo "用法: bash scripts/test_screener.sh <筛选器名称> [显示名称]"
    echo ""
    echo "参数:"
    echo "  筛选器名称    - 必需，数据库中的筛选器唯一标识符"
    echo "  显示名称      - 可选，UI 上显示的名称"
    echo ""
    echo "示例:"
    echo "  bash scripts/test_screener.sh lao_ya_tou_zhou_xian_screener \"老鸭头周线\""
    echo "  bash scripts/test_screener.sh coffee_cup_handle_screener_v4 \"咖啡杯柄 V4\""
    echo "  bash scripts/test_screener.sh ashare_21_screener"
    echo ""
    echo "常用筛选器:"
    echo "  lao_ya_tou_zhou_xian_screener    - 老鸭头周线"
    echo "  coffee_cup_handle_screener_v4    - 咖啡杯柄 V4"
    echo "  ashare_21_screener               - A股2.1"
    echo "  breakout_20day_screener           - 20天突破"
    echo "  breakout_main_screener            - 主升浪突破"
    exit 0
fi

# 获取参数
SCREENER_NAME="$1"
DISPLAY_NAME="${2:-$1}"  # 如果没有提供显示名称，使用筛选器名称

# 转到项目根目录
cd "$(dirname "$0")/.."

# 检查 Flask 是否运行
echo -e "${BLUE}检查 Flask Dashboard...${NC}"
if ! lsof -i :8765 > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Flask Dashboard 未运行，正在启动...${NC}"
    launchctl kickstart -k gui/$(id -u)/com.neotrade2.flask
    sleep 3

    if ! lsof -i :8765 > /dev/null 2>&1; then
        echo -e "${RED}❌ Flask Dashboard 启动失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Flask Dashboard 已启动${NC}"
else
    echo -e "${GREEN}✓ Flask Dashboard 正在运行${NC}"
fi

# 创建临时测试文件
TEMP_TEST_FILE="tests/test_${SCREENER_NAME}.spec.ts"
TEMP_TEST_FILE="${TEMP_TEST_FILE// /_}"  # 替换空格为下划线

echo ""
echo -e "${BLUE}创建测试文件: ${TEMP_TEST_FILE}${NC}"

# 基于模板创建测试文件
sed "s/TEMPLATE_SCREENER_NAME/${SCREENER_NAME}/g; s/TEMPLATE_DISPLAY_NAME/${DISPLAY_NAME}/g" \
    tests/screener-test-template.ts > "$TEMP_TEST_FILE"

echo -e "${GREEN}✓ 测试文件创建完成${NC}"

# 运行测试
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  开始测试筛选器${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}筛选器名称: ${SCREENER_NAME}${NC}"
echo -e "${BLUE}显示名称:   ${DISPLAY_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 运行 Playwright 测试
if npx playwright test "$TEMP_TEST_FILE" 2>&1 | tee /tmp/playwright_output.log; then
    # 测试成功
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✅ 筛选器测试完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}测试筛选器: ${DISPLAY_NAME} (${SCREENER_NAME})${NC}"
    echo -e "${GREEN}测试结果:   全部通过${NC}"
    echo -e "${GREEN}执行时间:   ${DURATION} 秒${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}查看详细报告:${NC}"
    echo -e "  npx playwright show-report"
    echo ""
else
    # 测试失败
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  ❌ 测试失败！${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}测试筛选器: ${DISPLAY_NAME} (${SCREENER_NAME})${NC}"
    echo -e "${RED}执行时间:   ${DURATION} 秒${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${BLUE}查看失败详情:${NC}"
    echo -e "  npx playwright show-report"
    echo ""
    echo -e "${BLUE}查看截图和视频:${NC}"
    echo -e "  ls -la test-results/"
    echo ""
fi

# 询问是否删除临时测试文件
read -p "$(echo -e ${YELLOW}是否删除临时测试文件? [Y/n]: ${NC})" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    rm -f "$TEMP_TEST_FILE"
    echo -e "${GREEN}✓ 临时测试文件已删除${NC}"
else
    echo -e "${YELLOW}临时测试文件保留: ${TEMP_TEST_FILE}${NC}"
fi

echo ""
echo -e "${BLUE}测试完成！${NC}"
