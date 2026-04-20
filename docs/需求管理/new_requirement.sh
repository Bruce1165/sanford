#!/bin/bash
# 快速创建新需求文档

echo "=== NeoTrade2 新需求创建向导 ==="
echo ""

# 获取需求编号
LAST_NUM=$(ls docs/需求管理/待评审/ docs/需求管理/进行中/ 2>/dev/null | grep -oE 'REQ_[0-9]+' | grep -oE '[0-9]+' | sort -n | tail -1)
NEXT_NUM=$((LAST_NUM + 1))
NEXT_ID=$(printf "REQ_%03d" $NEXT_NUM)

echo "下一步："
echo "1. 复制模板：cp docs/需求管理/需求提交模板.md docs/需求管理/待评审/${NEXT_ID}_功能名称.md"
echo "2. 参考示例：cat docs/需求管理/已完成/REQ_000_示例_跨筛选器股票跟踪.md"
echo "3. 填写需求：编辑 docs/需求管理/待评审/${NEXT_ID}_功能名称.md"
echo ""
echo "准备好的需求编号: $NEXT_ID"
echo ""
echo "是否现在创建新需求文档？(y/n)"
read -r answer

if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    echo ""
    echo "请输入功能名称（例如：跨筛选器股票跟踪）："
    read -r function_name

    FILE_PATH="docs/需求管理/待评审/${NEXT_ID}_${function_name}.md"
    cp docs/需求管理/需求提交模板.md "$FILE_PATH"

    echo ""
    echo "✓ 已创建需求文档: $FILE_PATH"
    echo "✓ 下一步：请编辑该文件，填写完整的需求描述"
    echo ""
    echo "参考示例：cat docs/需求管理/已完成/REQ_000_示例_跨筛选器股票跟踪.md"
else
    echo "已取消。"
fi
