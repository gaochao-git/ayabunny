"""TTS 代理 API - SiliconFlow IndexTTS-2 云端"""

import aiohttp
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from config import get_settings

router = APIRouter()
settings = get_settings()


class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str
    voice: str = "alex"  # IndexTTS-2 音色: alex, benjamin, charles, david, anna, bella, claire, diana


@router.post("/synthesize")
async def synthesize(request: TTSRequest):
    """
    TTS 文字转语音 - SiliconFlow IndexTTS-2 云端

    使用 SiliconFlow 的 IndexTTS-2 模型进行语音合成
    """
    try:
        # 获取 API Key（优先使用 TTS_API_KEY，否则使用 OPENAI_API_KEY）
        api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="未配置 TTS API Key")

        voice = request.voice or settings.TTS_VOICE or "alex"

        async with aiohttp.ClientSession() as session:
            # 构建 SiliconFlow TTS 请求
            payload = {
                "model": settings.TTS_MODEL,
                "input": request.text,
                "voice": f"{settings.TTS_MODEL}:{voice}",
                "response_format": "mp3"
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            print(f"[TTS] Synthesizing: {request.text[:50]}... with voice: {voice}")

            async with session.post(
                settings.TTS_BASE_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"[TTS] Error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"TTS 服务错误: {error_text}")

                audio_content = await response.read()
                print(f"[TTS] Generated {len(audio_content)} bytes audio (mp3)")

                # 返回 MP3 音频
                return Response(
                    content=audio_content,
                    media_type="audio/mpeg",
                    headers={"Content-Disposition": "attachment; filename=speech.mp3"}
                )

    except aiohttp.ClientError as e:
        print(f"[TTS] Client error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"TTS 服务连接失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TTS] Exception: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS 处理失败: {str(e)}")


@router.get("/health")
async def health():
    """检查 TTS 服务健康状态（云端服务默认健康）"""
    # SiliconFlow 云端服务，只要有 API Key 就认为健康
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    if api_key:
        return {"status": "healthy", "service": "tts", "provider": "siliconflow"}
    return {"status": "unhealthy", "service": "tts", "error": "no api key"}
