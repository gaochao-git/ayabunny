#!/bin/bash
# 重启所有服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

echo "=========================================="
echo "  语音助手 V2 - 重启服务"
echo "=========================================="

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "虚拟环境不存在，请先运行 setup.sh"
    exit 1
fi

# 停止所有服务
echo "停止旧服务..."
pkill -f "server/main.py" 2>/dev/null
pkill -f "vite.*voice_chat_local_v2" 2>/dev/null
sleep 2

# 启动后端
echo "[1/2] 启动后端 ($SERVER_PORT)..."
cd "$SCRIPT_DIR/server"
nohup $PYTHON -m uvicorn main:app --host 0.0.0.0 --port $SERVER_PORT > "$SCRIPT_DIR/logs/server.log" 2>&1 &
SERVER_PID=$!

sleep 3

# 启动前端
echo "[2/2] 启动前端 ($WEB_PORT)..."
cd "$SCRIPT_DIR/web"
npm run dev > "$SCRIPT_DIR/logs/web.log" 2>&1 &
WEB_PID=$!

sleep 3

# 状态检查
echo ""
echo "服务状态:"
echo "----------------------------------------"
lsof -i :$SERVER_PORT > /dev/null 2>&1 && echo "✓ 后端 Server  ($SERVER_PORT)" || echo "✗ 后端 Server  ($SERVER_PORT)"
lsof -i :$WEB_PORT > /dev/null 2>&1 && echo "✓ 前端 Web     ($WEB_PORT)" || echo "✗ 前端 Web     ($WEB_PORT)"
echo "----------------------------------------"
echo ""
echo "访问: http://localhost:$WEB_PORT"
echo ""
echo "日志:"
echo "  后端: tail -f $SCRIPT_DIR/logs/server.log"
echo "  前端: tail -f $SCRIPT_DIR/logs/web.log"
