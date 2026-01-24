#!/bin/bash
# 停止所有服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

echo "停止服务..."
pkill -f "server/main.py" 2>/dev/null
pkill -f "vite.*voice_chat_local_v2" 2>/dev/null

sleep 1

echo "服务状态:"
echo "----------------------------------------"
lsof -i :$SERVER_PORT > /dev/null 2>&1 && echo "✗ 后端仍在运行 ($SERVER_PORT)" || echo "✓ 后端已停止 ($SERVER_PORT)"
lsof -i :$WEB_PORT > /dev/null 2>&1 && echo "✗ 前端仍在运行 ($WEB_PORT)" || echo "✓ 前端已停止 ($WEB_PORT)"
echo "----------------------------------------"
