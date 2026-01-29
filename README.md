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

## 安装到手机

有两种方式将应用安装到手机：

| 方式 | PWA | Capacitor 原生 App |
|------|-----|-------------------|
| 安装方式 | 浏览器"添加到主屏幕" | Xcode / Android Studio 打包 |
| 上架应用商店 | ❌ 不能 | ✅ 可以 |
| 原生功能 | 有限 | 完整 |
| 签名/证书 | 不需要 | 需要 Apple ID |
| 更新方式 | 自动（刷新网页） | 重新打包安装 |
| 适用场景 | 快速分享、个人使用 | 正式发布、上架商店 |

---

## 方式一：PWA (Progressive Web App)

PWA 是最简单的方式，无需任何开发工具，直接通过浏览器安装。

### 已配置的 PWA 文件

- `web/public/manifest.json` - PWA 配置（名称、图标、主题色）
- `web/public/icon-192.png` - 小图标
- `web/public/icon-512.png` - 大图标
- `web/index.html` - PWA meta 标签

### iPhone 安装步骤

1. 用 **Safari** 打开网页（必须是 Safari，Chrome 不支持）
2. 点击底部 **分享按钮**（方框+箭头图标）
3. 滑动找到 **"添加到主屏幕"**
4. 点击 **"添加"**
5. 主屏幕会出现 App 图标

### Android 安装步骤

1. 用 **Chrome** 打开网页
2. 点击右上角 **菜单（三个点）**
3. 选择 **"添加到主屏幕"** 或 **"安装应用"**
4. 确认安装

### PWA 注意事项

- 需要 HTTPS（或 localhost）才能安装
- iOS Safari 对 PWA 支持有限（无后台运行、无推送通知）
- 更新自动生效，刷新页面即可

---

## 方式二：Capacitor 原生 App (iOS/Android)

使用 [Capacitor](https://capacitorjs.com/) 将 Web 应用打包为原生 App。

### 1. 安装 Capacitor

```bash
cd web

# 安装 Capacitor
npm install @capacitor/core @capacitor/cli @capacitor/ios @capacitor/android

# 初始化（已完成）
npx cap init "小智" "com.ayabunny.xiaozhi" --web-dir dist

# 添加平台
npx cap add ios
npx cap add android
```

### 2. 配置 API 地址

创建 `web/.env` 文件配置服务器地址：

```env
# API 服务器地址
VITE_API_BASE_URL=http://你的服务器IP

# WebSocket 地址
VITE_WS_BASE_URL=ws://你的服务器IP
VITE_VAD_WS_URL=ws://你的服务器IP/ws/vad
```

### 3. iOS 打包

**前提条件：**
- macOS 系统
- 安装 Xcode（App Store 下载）
- Apple ID（用于签名）

**配置 Info.plist 权限：**

`ios/App/App/Info.plist` 需要添加：

```xml
<!-- 允许 HTTP 连接（如果服务器没有 HTTPS） -->
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
    <key>NSAllowsArbitraryLoadsInWebContent</key>
    <true/>
    <key>NSAllowsLocalNetworking</key>
    <true/>
</dict>

<!-- 摄像头权限 -->
<key>NSCameraUsageDescription</key>
<string>小智需要访问摄像头来进行视频通话</string>

<!-- 麦克风权限 -->
<key>NSMicrophoneUsageDescription</key>
<string>小智需要访问麦克风来进行语音对话</string>

<!-- 语音识别权限 -->
<key>NSSpeechRecognitionUsageDescription</key>
<string>小智需要语音识别来理解您说的话</string>
```

**构建步骤：**

```bash
cd web

# 1. 构建 Web 应用
npm run build

# 2. 同步到 iOS 项目
npx cap sync ios

# 3. 打开 Xcode
npx cap open ios
```

**Xcode 配置：**

1. 选择左侧 **App** 项目 → **Signing & Capabilities**
2. 勾选 **Automatically manage signing**
3. Team 选择你的 Apple ID（点击 Add Account 添加）
4. 连接 iPhone，选择设备
5. 点击 **▶️ 运行** 安装到手机

**首次安装注意：**
- iPhone 需开启 **开发者模式**：设置 → 隐私与安全性 → 开发者模式
- 信任开发者证书：设置 → 通用 → VPN与设备管理 → 信任证书
- 免费 Apple ID 签名的 App 有效期 7 天

### 4. Android 打包

**前提条件：**
- 安装 Android Studio
- 配置 Android SDK

**构建步骤：**

```bash
cd web

# 1. 构建 Web 应用
npm run build

# 2. 同步到 Android 项目
npx cap sync android

# 3. 打开 Android Studio
npx cap open android
```

**生成 APK：**

1. Android Studio 菜单 → **Build → Build Bundle(s) / APK(s) → Build APK(s)**
2. 等待构建完成
3. APK 位置：`android/app/build/outputs/apk/debug/app-debug.apk`
4. 传输到手机安装（需允许安装未知来源应用）

### 5. 常见问题

**Q: iOS 报 SSL/ATS 错误？**

A: 确保 Info.plist 中配置了 `NSAllowsArbitraryLoads` 和 `NSAllowsArbitraryLoadsInWebContent`。如果使用 HTTPS 自签名证书，iOS 会拒绝连接，建议：
- 使用 HTTP（需配置 ATS 例外）
- 或使用有效的 SSL 证书（Let's Encrypt）

**Q: 国内服务器域名无法访问？**

A: 国内服务器使用域名需要 ICP 备案，未备案会被拦截。解决方案：
- 使用 IP 地址访问
- 或完成域名备案

**Q: 每次修改代码后如何更新？**

```bash
npm run build      # 重新构建
npx cap sync ios   # 同步到 iOS
# 然后在 Xcode 重新运行
```

### 6. 服务器 Nginx 配置示例

如果使用 Nginx 代理，配置参考：

```nginx
server {
    listen 80;
    server_name 你的服务器IP;
    client_max_body_size 100M;

    root /path/to/web/dist;

    # 静态文件
    location / {
        try_files $uri $uri/ @backend;
    }

    # API 代理
    location /api {
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }

    # WebSocket 代理
    location /ws {
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

## License

MIT
