#!/bin/bash

# 五子棋AI启动脚本
# 用法: bash start_ai.sh <port>

if [ -z "$1" ]; then
    echo "错误: 请指定端口号"
    echo "用法: bash start_ai.sh <port>"
    echo "示例: bash start_ai.sh 5000"
    exit 1
fi

PORT=$1
AI_ID="DevelopAI"
AI_NAME="Development AI"

echo "启动五子棋AI服务..."
echo "端口: $PORT"
echo "AI ID: $AI_ID"
echo "AI名称: $AI_NAME"
echo ""

python ai_service.py --port $PORT --ai_id $AI_ID --ai_name "$AI_NAME"
