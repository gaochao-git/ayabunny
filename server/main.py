"""语音助手后端服务入口"""

import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from config import get_settings
from api import api_router, ws_router
from agent.skills_loader import discover_skills

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时发现并加载技能
    print("[Server] 正在发现技能...")
    skills = discover_skills()
    print(f"[Server] 已发现 {len(skills)} 个技能")
    yield
    # 关闭时清理（如需要）
    print("[Server] 服务关闭")

# 创建 FastAPI 应用
app = FastAPI(
    title="语音助手 API",
    description="语音助手后端服务，提供对话、ASR、TTS 等功能",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
origins = settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)
# WebSocket 路由（/ws/vad）
app.include_router(ws_router, prefix="/ws", tags=["websocket"])


@app.get("/api/info")
async def api_info():
    """API 信息"""
    return {
        "service": "voice-chat-assistant",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


# 静态文件服务（前端构建产物）
FRONTEND_DIR = Path(__file__).parent.parent / "web" / "dist"
if FRONTEND_DIR.exists():
    # 静态资源目录（JS/CSS）
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    # 根路径
    @app.get("/", response_class=FileResponse)
    async def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")

    # 其他前端路由（排除 API/WS/health）
    @app.get("/{path:path}", response_class=FileResponse)
    async def serve_frontend(path: str):
        # 静态文件
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # SPA 回退
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
