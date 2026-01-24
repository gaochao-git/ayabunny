"""API 路由模块"""

from fastapi import APIRouter

from .chat import router as chat_router
from .asr import router as asr_router
from .tts import router as tts_router
from .skills import router as skills_router

api_router = APIRouter(prefix="/api")

api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(asr_router, prefix="/asr", tags=["asr"])
api_router.include_router(tts_router, prefix="/tts", tags=["tts"])
api_router.include_router(skills_router, prefix="/skills", tags=["skills"])
