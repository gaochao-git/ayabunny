#!/bin/bash
# 服务管理脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

start() {
    if lsof -i :$SERVER_PORT > /dev/null 2>&1; then
        echo "服务已在运行 (端口 $SERVER_PORT)"
        return 0
    fi
    echo "启动服务..."
    source $VENV_DIR/bin/activate
    cd "$SCRIPT_DIR/server"
    nohup python -m uvicorn main:app --host 0.0.0.0 --port $SERVER_PORT > "$LOG_DIR/server.log" 2>&1 &
    sleep 3
    if lsof -i :$SERVER_PORT > /dev/null 2>&1; then
        echo "✓ 服务已启动 (端口 $SERVER_PORT)"
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
