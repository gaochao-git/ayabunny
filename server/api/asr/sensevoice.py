"""SenseVoice ASR - SiliconFlow 云端"""

import aiohttp
from fastapi import HTTPException
from config import get_settings

settings = get_settings()



async def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    """使用 SiliconFlow SenseVoice 进行转写"""
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        raise HTTPException(status_code=503, detail="未配置 SiliconFlow API Key")

    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field('file', audio_bytes, filename=filename, content_type='audio/webm')
        data.add_field('model', settings.ASR_MODEL)

        headers = {'Authorization': f'Bearer {api_key}'}

        print(f"[ASR] SenseVoice 转写, 音频: {len(audio_bytes)} bytes")

        async with session.post(
            settings.ASR_BASE_URL,
            data=data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"[ASR] SenseVoice 错误: {error_text}")
                raise HTTPException(status_code=response.status, detail=f"SenseVoice 错误: {error_text}")

            result = await response.json()
            text = result.get("text", "").strip()
            print(f"[ASR] SenseVoice 结果: {text}")

            return {"success": True, "text": text, "service": "sensevoice"}


def is_available() -> bool:
    """检查服务是否可用"""
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    return bool(api_key)
