#!/bin/bash
# 初始化项目环境

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/config.sh"

echo "=========================================="
echo "  语音助手 V2 - 环境初始化"
echo "=========================================="

# 创建日志目录
mkdir -p "$SCRIPT_DIR/logs"

# 创建 Python 虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/4] 创建 Python 虚拟环境..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/4] 虚拟环境已存在"
fi

# 激活虚拟环境并安装依赖
echo "[2/4] 安装后端依赖..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/server/requirements.txt"

# 安装前端依赖
echo "[3/4] 安装前端依赖..."
cd "$SCRIPT_DIR/web"
if command -v pnpm &> /dev/null; then
    pnpm install
else
    npm install
fi

# 创建 .env 文件（如果不存在）
echo "[4/4] 检查配置文件..."
if [ ! -f "$SCRIPT_DIR/server/.env" ]; then
    if [ -f "$SCRIPT_DIR/server/.env.example" ]; then
        cp "$SCRIPT_DIR/server/.env.example" "$SCRIPT_DIR/server/.env"
        echo "  已创建 server/.env，请填写配置"
    fi
fi

echo ""
echo "=========================================="
echo "  初始化完成！"
echo "=========================================="
echo ""
echo "下一步:"
echo "  1. 编辑 server/.env 填写 API 配置"
echo "  2. 运行 ./restart.sh 启动服务"
