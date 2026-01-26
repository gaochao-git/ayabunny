"""Whisper ASR - 本地 faster-whisper"""

import asyncio
import tempfile
import os
from fastapi import HTTPException
from config import get_settings

settings = get_settings()

# 懒加载的模型实例
_model = None


def get_model():
    """懒加载 Whisper 模型"""
    global _model
    if _model is None:
        if not settings.WHISPER_ENABLED:
            raise HTTPException(status_code=503, detail="Whisper 未启用，请配置 WHISPER_ENABLED=true")
        try:
            from faster_whisper import WhisperModel
            print(f"[ASR] 加载 Whisper 模型: {settings.WHISPER_MODEL}")
            _model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")
            print(f"[ASR] Whisper 模型加载完成")
        except ImportError:
            raise HTTPException(status_code=503, detail="未安装 faster-whisper，请运行: pip install faster-whisper")
    return _model


def transcribe_sync(audio_bytes: bytes) -> dict:
    """同步转写（Whisper 不支持异步）"""
    model = get_model()

    # 写入临时文件（faster-whisper 需要文件路径）
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        segments, info = model.transcribe(temp_path, language="zh")
        text = "".join([segment.text for segment in segments]).strip()
        print(f"[ASR] Whisper 结果: {text}")
        return {"success": True, "text": text, "service": "whisper"}
    finally:
        os.unlink(temp_path)


async def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    """使用本地 Whisper 进行转写"""
    print(f"[ASR] Whisper 转写, 音频: {len(audio_bytes)} bytes")
    # 在线程池中运行同步代码
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, transcribe_sync, audio_bytes)


def is_available() -> bool:
    """检查服务是否可用"""
    return settings.WHISPER_ENABLED


def is_loaded() -> bool:
    """检查模型是否已加载"""
    return _model is not None
