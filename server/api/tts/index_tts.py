"""IndexTTS-2 - SiliconFlow 云端 TTS"""

import aiohttp
from fastapi import HTTPException
from config import get_settings

settings = get_settings()

MODEL_ID = "IndexTeam/IndexTTS-2"
TTS_URL = "https://api.siliconflow.cn/v1/audio/speech"

# 预设音色
PRESET_VOICES = ["alex", "benjamin", "charles", "david", "anna", "bella", "claire", "diana"]


async def synthesize(
    text: str,
    voice: str = "alex",
    speed: float = 1.0,
    reference_audio: str | None = None,
    reference_mime_type: str = "audio/mpeg"
) -> bytes:
    """
    使用 IndexTTS-2 进行语音合成

    Args:
        text: 要合成的文本
        voice: 预设音色（alex, benjamin 等）
        speed: 语速 (0.5-2.0)
        reference_audio: 参考音频 base64 编码（用于音色克隆）
        reference_mime_type: 参考音频的 MIME 类型

    Returns:
        音频数据 (mp3 格式)
    """
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="未配置 TTS API Key")

    # 构建请求
    payload = {
        "model": MODEL_ID,
        "input": text,
        "response_format": "mp3",
        "speed": max(0.5, min(2.0, speed)),
    }

    # 如果有参考音频，使用音色克隆模式
    if reference_audio:
        payload["references"] = [{
            "audio": f"data:{reference_mime_type};base64,{reference_audio}",
            "text": ""
        }]
        print(f"[TTS] IndexTTS-2 音色克隆模式，reference 长度: {len(reference_audio)} chars")
    else:
        payload["voice"] = f"{MODEL_ID}:{voice}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    print(f"[TTS] IndexTTS-2: {text[:50]}... voice={'clone' if reference_audio else voice}")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            TTS_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"[TTS] IndexTTS-2 错误: {error_text}")
                raise HTTPException(status_code=response.status, detail=f"IndexTTS-2 错误: {error_text}")

            audio_content = await response.read()
            print(f"[TTS] IndexTTS-2 生成 {len(audio_content)} bytes audio")
            return audio_content


def is_available() -> bool:
    """检查服务是否可用"""
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    return bool(api_key)
