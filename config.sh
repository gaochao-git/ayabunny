# 配置文件 - 根据实际情况修改

# 项目根目录
export PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python 虚拟环境
export VENV_DIR="$PROJECT_DIR/venv"
export PYTHON="$VENV_DIR/bin/python"
export PIP="$VENV_DIR/bin/pip"

# 端口配置
export SERVER_PORT=6002    # FastAPI 后端
export WEB_PORT=6001       # Vue 前端 (vite dev)

# ASR/TTS 外部服务（复用 v1 的服务）
export ASR_URL="http://localhost:8012"
export TTS_URL="http://localhost:8013"

# LLM 配置（从 .env 读取，这里只是说明）
# OPENAI_API_KEY=xxx
# OPENAI_BASE_URL=xxx
# OPENAI_MODEL=xxx
