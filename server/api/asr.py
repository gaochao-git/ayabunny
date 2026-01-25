"""ASR API

支持多种 ASR 服务（优先级从高到低）：
1. SiliconFlow SenseVoice - 云端，免费，中文优秀
2. 外部 FunASR - 需要单独启动服务
"""

import aiohttp
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import get_settings

router = APIRouter()
settings = get_settings()

# ============ SiliconFlow ASR（云端，推荐）============

SILICONFLOW_ASR_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
SILICONFLOW_ASR_MODEL = "FunAudioLLM/SenseVoiceSmall"  # 免费模型


async def transcribe_with_siliconflow(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    """使用 SiliconFlow SenseVoice 进行转写（云端）"""
    # 获取 API Key（复用 TTS 或 LLM 的 key）
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        raise HTTPException(status_code=503, detail="未配置 SiliconFlow API Key")

    async with aiohttp.ClientSession() as session:
        # 构建 multipart 表单
        data = aiohttp.FormData()
        data.add_field(
            'file',
            audio_bytes,
            filename=filename,
            content_type='audio/webm'
        )
        data.add_field('model', SILICONFLOW_ASR_MODEL)

        headers = {
            'Authorization': f'Bearer {api_key}'
        }

        print(f"[ASR] 调用 SiliconFlow SenseVoice, 音频大小: {len(audio_bytes)} bytes")

        async with session.post(
            SILICONFLOW_ASR_URL,
            data=data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            print(f"[ASR] SiliconFlow 响应状态: {response.status}")

            if response.status != 200:
                error_text = await response.text()
                print(f"[ASR] SiliconFlow 错误: {error_text}")
                raise HTTPException(
                    status_code=response.status,
                    detail=f"SiliconFlow ASR 错误: {error_text}"
                )

            result = await response.json()
            text = result.get("text", "")
            print(f"[ASR] SiliconFlow 识别结果: {text}")

            return {
                "success": True,
                "text": text.strip(),
                "service": "siliconflow"
            }


# ============ 外部 FunASR 服务（备用）============

async def transcribe_with_funasr(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    """使用外部 FunASR 服务进行转写"""
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field(
            'audio',
            audio_bytes,
            filename=filename,
            content_type='audio/webm'
        )

        print(f"[ASR] 调用外部 FunASR: {settings.ASR_BASE_URL}")

        async with session.post(
            f"{settings.ASR_BASE_URL}/transcribe",
            data=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            print(f"[ASR] FunASR 响应状态: {response.status}")

            if response.status != 200:
                error_text = await response.text()
                print(f"[ASR] FunASR 错误: {error_text}")
                raise HTTPException(
                    status_code=response.status,
                    detail=f"FunASR 服务错误: {error_text}"
                )

            result = await response.json()
            text = result.get("text", "")
            print(f"[ASR] FunASR 识别结果: {text}")

            return {
                "success": True,
                "text": text,
                "segments": result.get("segments", []),
                "service": "funasr"
            }


# ============ API 端点 ============

@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    ASR 语音转文字

    优先使用 SiliconFlow 云端 ASR（免费、快速）
    """
    try:
        audio_bytes = await audio.read()
        print(f"[ASR] 收到音频: {len(audio_bytes)} bytes, filename: {audio.filename}")

        # 优先使用 SiliconFlow
        try:
            return await transcribe_with_siliconflow(audio_bytes, audio.filename or "audio.webm")
        except HTTPException as e:
            if e.status_code == 503:  # API Key 未配置
                print("[ASR] SiliconFlow 不可用，尝试外部 FunASR")
            else:
                raise

        # 备用：外部 FunASR
        return await transcribe_with_funasr(audio_bytes, audio.filename or "audio.webm")

    except HTTPException:
        raise
    except aiohttp.ClientError as e:
        print(f"[ASR] 网络错误: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"ASR 服务连接失败: {str(e)}")
    except Exception as e:
        print(f"[ASR] 异常: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ASR 处理失败: {str(e)}")


@router.post("/siliconflow/transcribe")
async def siliconflow_transcribe(audio: UploadFile = File(...)):
    """
    SiliconFlow ASR 语音转文字（云端 SenseVoice）
    """
    try:
        audio_bytes = await audio.read()
        print(f"[ASR] SiliconFlow 收到音频: {len(audio_bytes)} bytes")
        return await transcribe_with_siliconflow(audio_bytes, audio.filename or "audio.webm")

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ASR] SiliconFlow 异常: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ASR 处理失败: {str(e)}")


@router.get("/health")
async def health():
    """检查 ASR 服务健康状态"""
    # 检查 SiliconFlow
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    if api_key:
        return {"status": "healthy", "service": "siliconflow", "model": SILICONFLOW_ASR_MODEL}

    # 检查外部 FunASR
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

    return {"status": "unhealthy", "service": "none"}
