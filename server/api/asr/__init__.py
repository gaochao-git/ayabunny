"""ASR API

支持多种 ASR 服务：
1. SenseVoice - SiliconFlow 云端，免费，中文优秀（默认）
2. Whisper - 本地 faster-whisper，需配置 WHISPER_ENABLED=true
3. FunASR - 本地 FunASR，需配置 FUNASR_ENABLED=true
"""

from fastapi import APIRouter, UploadFile, File
from config import get_settings

from . import sensevoice, whisper, funasr

router = APIRouter()
settings = get_settings()


# ============ API 端点 ============

@router.post("/sensevoice/transcribe")
async def sensevoice_transcribe(audio: UploadFile = File(...)):
    """SenseVoice ASR (SiliconFlow 云端)"""
    audio_bytes = await audio.read()
    print(f"[ASR] SenseVoice 收到音频: {len(audio_bytes)} bytes")
    return await sensevoice.transcribe(audio_bytes, audio.filename or "audio.webm")


@router.post("/whisper/transcribe")
async def whisper_transcribe(audio: UploadFile = File(...)):
    """Whisper ASR (本地 faster-whisper)"""
    audio_bytes = await audio.read()
    print(f"[ASR] Whisper 收到音频: {len(audio_bytes)} bytes")
    return await whisper.transcribe(audio_bytes, audio.filename or "audio.webm")


@router.post("/funasr/transcribe")
async def funasr_transcribe(audio: UploadFile = File(...)):
    """FunASR (本地服务)"""
    audio_bytes = await audio.read()
    print(f"[ASR] FunASR 收到音频: {len(audio_bytes)} bytes")
    return await funasr.transcribe(audio_bytes, audio.filename or "audio.webm")


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """默认 ASR 端点 (使用 SenseVoice)"""
    audio_bytes = await audio.read()
    print(f"[ASR] 收到音频: {len(audio_bytes)} bytes")
    return await sensevoice.transcribe(audio_bytes, audio.filename or "audio.webm")


@router.get("/health")
async def health():
    """检查 ASR 服务健康状态"""
    services = []

    # 检查 SenseVoice（云端）
    if sensevoice.is_available():
        services.append({"name": "sensevoice", "status": "available", "type": "cloud"})

    # 检查 Whisper（本地）
    if whisper.is_available():
        status = "loaded" if whisper.is_loaded() else "enabled"
        services.append({"name": "whisper", "status": status, "type": "local", "model": settings.WHISPER_MODEL})
    else:
        services.append({"name": "whisper", "status": "disabled", "type": "local"})

    # 检查 FunASR（本地）
    if funasr.is_available():
        status = "loaded" if funasr.is_loaded() else "enabled"
        services.append({"name": "funasr", "status": status, "type": "local"})
    else:
        services.append({"name": "funasr", "status": "disabled", "type": "local"})

    return {"services": services}
