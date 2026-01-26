"""TTS API

支持多种 TTS 模型：
1. IndexTTS-2 - SiliconFlow 云端，多音色，支持克隆（默认）
2. CosyVoice 2 - SiliconFlow 云端，阿里开源，中文效果好
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from config import get_settings

from . import index_tts, cosyvoice, voices

router = APIRouter()
settings = get_settings()

# 模型映射
MODELS = {
    "IndexTeam/IndexTTS-2": index_tts,
    "FunAudioLLM/CosyVoice2-0.5B": cosyvoice,
}


class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str
    model: Optional[str] = None  # TTS 模型
    voice: str = "alex"  # 预设音色
    custom_voice_id: Optional[str] = None  # 自定义音色 ID
    speed: float = 1.0  # 语速 (0.5-2.0)


# ============ API 端点 ============

@router.post("/synthesize")
async def synthesize(request: TTSRequest):
    """
    TTS 文字转语音 - SiliconFlow 云端

    支持模型：
    - IndexTeam/IndexTTS-2: 多音色，支持克隆
    - FunAudioLLM/CosyVoice2-0.5B: 阿里开源，中文效果好
    """
    try:
        # 选择模型
        model_id = request.model or settings.TTS_MODEL
        model_module = MODELS.get(model_id)
        if not model_module:
            raise HTTPException(status_code=400, detail=f"不支持的模型: {model_id}")

        # 处理自定义音色
        reference_audio = None
        reference_mime_type = "audio/mpeg"

        if request.custom_voice_id:
            custom_voice = voices.get_voice_by_id(request.custom_voice_id)
            if custom_voice:
                reference_audio = voices.load_voice_audio_base64(custom_voice)
                reference_mime_type = voices.get_voice_mime_type(custom_voice)
                if reference_audio:
                    print(f"[TTS] 使用自定义音色: {custom_voice['name']}")
                else:
                    print(f"[TTS] 音色文件不存在: {custom_voice['audio_file']}")

        # 调用模型合成
        audio_content = await model_module.synthesize(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
            reference_audio=reference_audio,
            reference_mime_type=reference_mime_type,
        )

        return Response(
            content=audio_content,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=speech.mp3"}
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[TTS] Exception: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS 处理失败: {str(e)}")


# 音色管理子路由
router.include_router(voices.router, prefix="/voices", tags=["voices"])


# 音色测试端点
@router.post("/voices/{voice_id}/test")
async def test_voice(voice_id: str, request: voices.TestVoiceRequest):
    """测试自定义音色"""
    tts_request = TTSRequest(text=request.text, custom_voice_id=voice_id)
    return await synthesize(tts_request)


@router.get("/health")
async def health():
    """检查 TTS 服务健康状态"""
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    if api_key:
        return {
            "status": "healthy",
            "service": "tts",
            "models": list(MODELS.keys()),
            "default_model": settings.TTS_MODEL
        }
    return {"status": "unhealthy", "service": "tts", "error": "no api key"}
