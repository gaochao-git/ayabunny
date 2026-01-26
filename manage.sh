#!/bin/bash
# 服务管理脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
LOG_DIR="$SCRIPT_DIR/logs"

# 从 .env 读取端口，默认 8888
if [ -f "$SCRIPT_DIR/server/.env" ]; then
    SERVER_PORT=$(grep "^PORT=" "$SCRIPT_DIR/server/.env" | cut -d'=' -f2)
fi
SERVER_PORT=${SERVER_PORT:-8888}

# 检查 venv 环境
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        echo "✗ 虚拟环境不存在: $VENV_DIR"
        echo ""
        echo "请先创建虚拟环境:"
        echo "  cd $SCRIPT_DIR"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -r server/requirements.txt"
        exit 1
    fi
}

start() {
    check_venv
    if lsof -i :$SERVER_PORT > /dev/null 2>&1; then
        echo "服务已在运行 (端口 $SERVER_PORT)"
        return 0
    fi
    echo "启动服务 (端口 $SERVER_PORT)..."
    source "$VENV_DIR/bin/activate"
    cd "$SCRIPT_DIR/server"
    mkdir -p "$LOG_DIR"
    nohup python -m uvicorn main:app --host 0.0.0.0 --port $SERVER_PORT > "$LOG_DIR/server.log" 2>&1 &
    sleep 3
    if lsof -i :$SERVER_PORT > /dev/null 2>&1; then
        echo "✓ 服务已启动"
    else
        echo "✗ 启动失败，查看日志: cat $LOG_DIR/server.log"
    fi
}

stop() {
    echo "停止服务..."
    lsof -ti:$SERVER_PORT | xargs kill -9 2>/dev/null
    sleep 1
    if lsof -i :$SERVER_PORT > /dev/null 2>&1; then
        echo "✗ 停止失败"
    else
        echo "✓ 服务已停止"
    fi
}

restart() {
    stop
    sleep 1
    start
}

status() {
    if lsof -i :$SERVER_PORT > /dev/null 2>&1; then
        echo "✓ 服务运行中 (端口 $SERVER_PORT)"
        echo "  PID: $(lsof -ti:$SERVER_PORT)"
    else
        echo "✗ 服务未运行"
    fi
}

logs() {
    tail -f "$LOG_DIR/server.log"
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    status)  status ;;
    logs)    logs ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
