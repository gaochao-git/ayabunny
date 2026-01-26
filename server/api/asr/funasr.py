"""FunASR - 本地服务"""

import asyncio
import tempfile
import os
from fastapi import HTTPException
from config import get_settings

settings = get_settings()

# 懒加载的模型实例
_model = None


def get_model():
    """懒加载 FunASR 模型"""
    global _model
    if _model is None:
        if not settings.FUNASR_ENABLED:
            raise HTTPException(status_code=503, detail="FunASR 未启用，请配置 FUNASR_ENABLED=true")
        try:
            from funasr import AutoModel
            print(f"[ASR] 加载 FunASR 模型")
            _model = AutoModel(model="paraformer-zh", model_revision="v2.0.4")
            print(f"[ASR] FunASR 模型加载完成")
        except ImportError:
            raise HTTPException(status_code=503, detail="未安装 funasr，请运行: pip install funasr")
    return _model


def transcribe_sync(audio_bytes: bytes) -> dict:
    """同步转写"""
    model = get_model()

    # 写入临时文件
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name

    try:
        result = model.generate(input=temp_path)
        text = result[0]["text"] if result else ""
        print(f"[ASR] FunASR 结果: {text}")
        return {"success": True, "text": text, "service": "funasr"}
    finally:
        os.unlink(temp_path)


async def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    """使用本地 FunASR 进行转写"""
    print(f"[ASR] FunASR 转写, 音频: {len(audio_bytes)} bytes")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, transcribe_sync, audio_bytes)


def is_available() -> bool:
    """检查服务是否可用"""
    return settings.FUNASR_ENABLED


def is_loaded() -> bool:
    """检查模型是否已加载"""
    return _model is not None
