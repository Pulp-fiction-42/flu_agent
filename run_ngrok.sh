#!/bin/bash
# FluAgent ngrok 启动脚本
# 使用 ngrok 暴露公网访问

set -e

echo "=========================================="
echo " FluAgent - ngrok 启动脚本"
echo "=========================================="

# 检查 pyngrok 是否安装
if ! python -c "import pyngrok" 2>/dev/null; then
    echo "错误: pyngrok 未安装"
    echo "请先安装: pip install pyngrok"
    echo ""
    echo "如需使用 ngrok，还需要："
    echo "1. 注册 ngrok 账号: https://ngrok.com/"
    echo "2. 获取 authtoken"
    echo "3. 配置: ngrok config add-authtoken <your-token>"
    exit 1
fi

# 检查 ngrok 是否配置
if ! ngrok authtoken 2>/dev/null; then
    echo "警告: ngrok authtoken 未配置"
    echo "请先配置: ngrok config add-authtoken <your-token>"
    echo "获取 token: https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
fi

PORT=${1:-7861}
echo "使用端口: $PORT"

echo ""
echo "启动 FluAgent Web 服务..."
echo ""

# 启动 ngrok 和 FluAgent
python run.py --mode web --port $PORT --ngrok
