#!/bin/bash

if [ "$#" -ne 1 ]; then
  echo "Usage: bash start_ai.sh <port>"
  exit 1
fi

PORT=$1
python3 ai_service.py $PORT