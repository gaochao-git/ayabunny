"""ASR 代理 API

支持多种 ASR 服务：
- FunASR: 阿里达摩院，中文识别效果好
- Whisper: OpenAI，多语言支持好
"""

import aiohttp
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import get_settings

router = APIRouter()
settings = get_settings()

# Whisper 服务地址
WHISPER_BASE_URL = "http://127.0.0.1:8017"


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    ASR 语音转文字代理

    接收音频文件，转发到本地 FunASR 服务进行识别
    注意：使用 aiohttp 而非 httpx，因为 httpx 与 FunASR 服务不兼容
    """
    try:
        audio_bytes = await audio.read()
        print(f"[ASR] Received audio: {len(audio_bytes)} bytes, filename: {audio.filename}, content_type: {audio.content_type}")

        async with aiohttp.ClientSession() as session:
            # 构建 multipart 表单数据
            # 注意：保持原始文件名和 content-type，FunASR 支持 webm 格式
            data = aiohttp.FormData()
            data.add_field(
                'audio',
                audio_bytes,
                filename=audio.filename or 'audio.webm',
                content_type=audio.content_type or 'audio/webm'
            )

            print(f"[ASR] Forwarding to {settings.ASR_BASE_URL}/transcribe")
            async with session.post(
                f"{settings.ASR_BASE_URL}/transcribe",
                data=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                print(f"[ASR] Response status: {response.status}")

                if response.status != 200:
                    error_text = await response.text()
                    print(f"[ASR] Error response: {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"ASR 服务错误: {error_text}")

                result = await response.json()
                print(f"[ASR] Result: {result}")

                return {
                    "success": True,
                    "text": result.get("text", ""),
                    "segments": result.get("segments", [])
                }

    except aiohttp.ClientError as e:
        print(f"[ASR] Client error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"ASR 服务连接失败: {str(e)}")
    except Exception as e:
        print(f"[ASR] Exception: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ASR 处理失败: {str(e)}")


@router.get("/health")
async def health():
    """检查 FunASR 服务健康状态"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.ASR_BASE_URL}/",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    return {"status": "healthy", "service": "funasr"}
    except Exception:
        pass
    return {"status": "unhealthy", "service": "funasr"}


@router.post("/whisper/transcribe")
async def whisper_transcribe(audio: UploadFile = File(...)):
    """
    Whisper ASR 语音转文字代理

    接收音频文件，转发到本地 Whisper 服务进行识别
    """
    try:
        audio_bytes = await audio.read()
        print(f"[Whisper ASR] Received audio: {len(audio_bytes)} bytes, filename: {audio.filename}")

        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field(
                'audio',
                audio_bytes,
                filename=audio.filename or 'audio.webm',
                content_type=audio.content_type or 'audio/webm'
            )

            print(f"[Whisper ASR] Forwarding to {WHISPER_BASE_URL}/transcribe")
            async with session.post(
                f"{WHISPER_BASE_URL}/transcribe",
                data=data,
                timeout=aiohttp.ClientTimeout(total=60)  # Whisper 可能需要更长时间
            ) as response:
                print(f"[Whisper ASR] Response status: {response.status}")

                if response.status != 200:
                    error_text = await response.text()
                    print(f"[Whisper ASR] Error response: {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"Whisper 服务错误: {error_text}")

                result = await response.json()
                print(f"[Whisper ASR] Result: {result}")

                return {
                    "success": True,
                    "text": result.get("text", ""),
                    "segments": result.get("segments", [])
                }

    except aiohttp.ClientError as e:
        print(f"[Whisper ASR] Client error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Whisper 服务连接失败: {str(e)}")
    except Exception as e:
        print(f"[Whisper ASR] Exception: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Whisper 处理失败: {str(e)}")


@router.get("/whisper/health")
async def whisper_health():
    """检查 Whisper 服务健康状态"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{WHISPER_BASE_URL}/",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    return {"status": "healthy", "service": "whisper"}
    except Exception:
        pass
    return {"status": "unhealthy", "service": "whisper"}
