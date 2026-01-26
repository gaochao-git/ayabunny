"""CosyVoice 2 - SiliconFlow 云端 TTS"""

import aiohttp
from fastapi import HTTPException
from config import get_settings

settings = get_settings()

MODEL_ID = "FunAudioLLM/CosyVoice2-0.5B"
TTS_URL = "https://api.siliconflow.cn/v1/audio/speech"

# CosyVoice 2 预设音色（与 IndexTTS 不同）
PRESET_VOICES = ["中文女", "中文男", "英文女", "英文男", "日语男", "粤语女", "韩语女"]


async def synthesize(
    text: str,
    voice: str = "中文女",
    speed: float = 1.0,
    reference_audio: str | None = None,
    reference_mime_type: str = "audio/mpeg"
) -> bytes:
    """
    使用 CosyVoice 2 进行语音合成

    Args:
        text: 要合成的文本
        voice: 预设音色（中文女、中文男等）
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
        print(f"[TTS] CosyVoice2 音色克隆模式，reference 长度: {len(reference_audio)} chars")
    else:
        payload["voice"] = f"{MODEL_ID}:{voice}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    print(f"[TTS] CosyVoice2: {text[:50]}... voice={'clone' if reference_audio else voice}")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            TTS_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"[TTS] CosyVoice2 错误: {error_text}")
                raise HTTPException(status_code=response.status, detail=f"CosyVoice2 错误: {error_text}")

            audio_content = await response.read()
            print(f"[TTS] CosyVoice2 生成 {len(audio_content)} bytes audio")
            return audio_content


def is_available() -> bool:
    """检查服务是否可用"""
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    return bool(api_key)
