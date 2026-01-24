# 语音助手 Voice Chat Local

基于 Vue 3 + FastAPI + LangChain 的语音助手应用，支持语音对话和故事讲述。

## 功能特点

- 语音通话：支持语音输入、TTS 播放
- 技能系统：LLM 自动判断是否调用技能 Tool
- 故事管理：支持添加、编辑、删除故事
- 流式响应：SSE 实时流式输出

## 技术栈

**后端：**
- Python 3.10+
- FastAPI
- LangChain 0.3+
- httpx（ASR/TTS 代理）

**前端：**
- Vue 3 + Composition API
- TypeScript
- Vite
- Pinia（状态管理）
- TailwindCSS

## 快速开始

### 1. 后端

```bash
cd server

# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 等配置

# 启动服务
python main.py
```

后端服务运行在 http://127.0.0.1:5002

### 2. 前端

```bash
cd web

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

前端服务运行在 http://127.0.0.1:3001

### 3. 外部服务（可选）

如需使用语音功能，需要启动：

- **ASR 服务**：FunASR 服务，默认端口 10095
- **TTS 服务**：GPT-SoVITS 服务，默认端口 9880

## 目录结构

```
voice_chat_local/
├── server/                     # FastAPI 后端
│   ├── main.py                 # 入口
│   ├── config.py               # 配置
│   ├── api/                    # API 路由
│   │   ├── chat.py             # 对话 API（SSE 流式）
│   │   ├── asr.py              # ASR 代理
│   │   ├── tts.py              # TTS 代理
│   │   └── skills.py           # 技能管理 API
│   ├── agent/                  # LangChain Agent
│   │   ├── agent.py            # Agent 定义
│   │   └── tools/
│   │       └── storytelling.py # 讲故事 Tool
│   └── skills/                 # 技能数据
│       └── storytelling/
│           ├── index.json
│           └── stories/*.md
│
└── web/                        # Vue 前端
    ├── src/
    │   ├── api/                # API 调用
    │   ├── composables/        # 可复用逻辑
    │   ├── components/         # 组件
    │   ├── views/              # 页面
    │   └── stores/             # 状态管理
    └── ...
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | SSE 流式对话 |
| `/api/chat/simple` | POST | 非流式对话 |
| `/api/asr/transcribe` | POST | ASR 语音转文字 |
| `/api/tts/synthesize` | POST | TTS 文字转语音 |
| `/api/skills` | GET | 获取技能列表 |
| `/api/skills/{id}/stories` | GET/POST | 故事列表/创建 |
| `/api/skills/{id}/stories/{story_id}` | GET/PUT/DELETE | 故事 CRUD |

## 使用说明

1. **文本对话**：在输入框输入文字，点击发送
2. **语音通话**：点击电话图标开始语音通话
3. **故事管理**：点击右上角书本图标进入管理页面

## 环境变量

后端 `.env`：

```env
# LLM 配置
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus

# ASR/TTS 服务地址
ASR_BASE_URL=http://127.0.0.1:10095
TTS_BASE_URL=http://127.0.0.1:9880
```

## License

MIT
