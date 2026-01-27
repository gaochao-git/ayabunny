#!/bin/bash
# 发布脚本 - 发布前端/后端到服务器

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_HOST="root@62.234.152.217"
SERVER_DIR="/data/ayabunny"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[发布]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

# 发布前端
release_web() {
    log "构建前端..."
    cd "$SCRIPT_DIR/web"
    npm run build

    log "上传前端到服务器..."
    scp -r dist/* "$SERVER_HOST:$SERVER_DIR/web/dist/"

    log "前端发布完成"
}

# 发布后端
release_server() {
    log "提交代码..."
    cd "$SCRIPT_DIR"

    # 检查是否有未提交的更改
    if [[ -n $(git status -s) ]]; then
        git add -A
        git commit -m "release: 更新代码

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
    fi

    log "推送到远程仓库..."
    git push

    log "服务器拉取代码..."
    ssh "$SERVER_HOST" "cd $SERVER_DIR && git pull"

    log "重启服务..."
    ssh "$SERVER_HOST" "cd $SERVER_DIR && ./manage.sh restart"

    log "后端发布完成"
}

# 显示帮助
show_help() {
    echo "用法: $0 [web|server|all]"
    echo ""
    echo "  web     发布前端 (构建并上传 dist)"
    echo "  server  发布后端 (git push + 服务器 pull + 重启)"
    echo "  all     发布前端和后端"
    echo ""
    echo "示例:"
    echo "  $0 web      # 只发布前端"
    echo "  $0 server   # 只发布后端"
    echo "  $0 all      # 发布全部"
}

case "$1" in
    web)
        release_web
        ;;
    server)
        release_server
        ;;
    all)
        release_server
        release_web
        ;;
    *)
        show_help
        exit 1
        ;;
esac

echo ""
log "发布完成! 访问: https://62.234.152.217"
