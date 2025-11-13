#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: bash start_ai.sh <port>"
    exit 1
fi

PORT=$1
python ai_service.py --port $PORT