# 配置文件

# 项目根目录
export PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python 虚拟环境
export VENV_DIR="$PROJECT_DIR/venv"

# 端口配置
export SERVER_PORT=8888

# 日志目录
export LOG_DIR="$PROJECT_DIR/logs"
