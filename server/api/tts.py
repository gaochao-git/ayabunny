"""TTS 代理 API - SiliconFlow IndexTTS-2 云端 + 音色克隆"""

import os
import json
import uuid
import base64
import aiohttp
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel
from typing import Optional
from config import get_settings

router = APIRouter()
settings = get_settings()

# 自定义音色存储目录
VOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voices")
os.makedirs(VOICES_DIR, exist_ok=True)


class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str
    voice: str = "alex"  # IndexTTS-2 音色或自定义音色 ID
    custom_voice_id: Optional[str] = None  # 自定义音色 ID（优先级高于 voice）


class CustomVoice(BaseModel):
    """自定义音色"""
    id: str
    name: str
    description: str = ""
    created_at: str
    audio_file: str  # 音频文件名
    duration: float = 0  # 音频时长（秒）


def get_voices_index_path():
    """获取音色索引文件路径"""
    return os.path.join(VOICES_DIR, "index.json")


def load_voices_index() -> list[dict]:
    """加载音色索引"""
    index_path = get_voices_index_path()
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_voices_index(voices: list[dict]):
    """保存音色索引"""
    index_path = get_voices_index_path()
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(voices, f, ensure_ascii=False, indent=2)


@router.post("/synthesize")
async def synthesize(request: TTSRequest):
    """
    TTS 文字转语音 - SiliconFlow IndexTTS-2 云端

    支持：
    - 预设音色：alex, benjamin, charles, david, anna, bella, claire, diana
    - 自定义克隆音色：通过 custom_voice_id 指定
    """
    try:
        # 获取 API Key
        api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="未配置 TTS API Key")

        voice = request.voice or settings.TTS_VOICE or "alex"
        reference_audio = None

        # 如果指定了自定义音色，加载参考音频
        if request.custom_voice_id:
            voices = load_voices_index()
            custom_voice = next((v for v in voices if v["id"] == request.custom_voice_id), None)
            if custom_voice:
                audio_path = os.path.join(VOICES_DIR, custom_voice["audio_file"])
                if os.path.exists(audio_path):
                    with open(audio_path, "rb") as f:
                        audio_data = f.read()
                        reference_audio = base64.b64encode(audio_data).decode("utf-8")
                    print(f"[TTS] 使用自定义音色: {custom_voice['name']}, 文件: {audio_path}, 大小: {len(audio_data)} bytes")
                else:
                    print(f"[TTS] 音色文件不存在: {audio_path}")

        async with aiohttp.ClientSession() as session:
            # 构建 SiliconFlow TTS 请求
            payload = {
                "model": settings.TTS_MODEL,
                "input": request.text,
                "response_format": "mp3"
            }

            # 如果有参考音频，使用音色克隆模式
            if reference_audio:
                # SiliconFlow 使用 references 数组格式
                # audio 需要 data URI 前缀
                audio_ext = custom_voice["audio_file"].split(".")[-1].lower()
                mime_type = {
                    "mp3": "audio/mpeg",
                    "wav": "audio/wav",
                    "webm": "audio/webm",
                }.get(audio_ext, "audio/mpeg")

                payload["references"] = [{
                    "audio": f"data:{mime_type};base64,{reference_audio}",
                    "text": ""  # 参考音频的文本内容（可选）
                }]
                print(f"[TTS] 使用 references 模式，audio 长度: {len(reference_audio)} chars")
            else:
                payload["voice"] = f"{settings.TTS_MODEL}:{voice}"

            print(f"[TTS] 请求 payload keys: {list(payload.keys())}")

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            print(f"[TTS] Synthesizing: {request.text[:50]}... with {'custom voice' if reference_audio else voice}")

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


# ========== 自定义音色管理 ==========

@router.get("/voices")
async def list_voices():
    """获取所有自定义音色列表"""
    voices = load_voices_index()
    return {"voices": voices}


@router.post("/voices")
async def create_voice(
    audio: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form("")
):
    """
    创建自定义音色（上传参考音频）

    - audio: 参考音频文件（支持 mp3, wav, webm）
    - name: 音色名称
    - description: 音色描述
    """
    # 验证文件类型
    allowed_types = ["audio/mpeg", "audio/wav", "audio/webm", "audio/mp3", "audio/x-wav"]
    if audio.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"不支持的音频格式: {audio.content_type}")

    # 生成唯一 ID
    voice_id = str(uuid.uuid4())[:8]

    # 确定文件扩展名
    ext_map = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/webm": ".webm",
    }
    ext = ext_map.get(audio.content_type, ".mp3")

    # 保存音频文件
    audio_filename = f"{voice_id}{ext}"
    audio_path = os.path.join(VOICES_DIR, audio_filename)

    content = await audio.read()
    with open(audio_path, "wb") as f:
        f.write(content)

    print(f"[TTS] 保存音色文件: {audio_path}, 大小: {len(content)} bytes")

    # 创建音色记录
    voice_data = {
        "id": voice_id,
        "name": name,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "audio_file": audio_filename,
        "duration": 0  # TODO: 计算音频时长
    }

    # 更新索引
    voices = load_voices_index()
    voices.append(voice_data)
    save_voices_index(voices)

    print(f"[TTS] 创建自定义音色: {name} ({voice_id})")
    return {"success": True, "voice": voice_data}


@router.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    """删除自定义音色"""
    voices = load_voices_index()
    voice = next((v for v in voices if v["id"] == voice_id), None)

    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")

    # 删除音频文件
    audio_path = os.path.join(VOICES_DIR, voice["audio_file"])
    if os.path.exists(audio_path):
        os.remove(audio_path)

    # 更新索引
    voices = [v for v in voices if v["id"] != voice_id]
    save_voices_index(voices)

    print(f"[TTS] 删除自定义音色: {voice['name']} ({voice_id})")
    return {"success": True}


@router.get("/voices/{voice_id}/audio")
async def get_voice_audio(voice_id: str):
    """获取音色的参考音频"""
    voices = load_voices_index()
    voice = next((v for v in voices if v["id"] == voice_id), None)

    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")

    audio_path = os.path.join(VOICES_DIR, voice["audio_file"])
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")

    # 确定 MIME 类型
    ext = os.path.splitext(voice["audio_file"])[1].lower()
    media_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
    }
    media_type = media_types.get(ext, "audio/mpeg")

    return FileResponse(audio_path, media_type=media_type)


class TestVoiceRequest(BaseModel):
    """测试音色请求"""
    text: str = "你好，这是一段测试语音。"


@router.post("/voices/{voice_id}/test")
async def test_voice(voice_id: str, request: TestVoiceRequest):
    """测试自定义音色"""
    tts_request = TTSRequest(text=request.text, custom_voice_id=voice_id)
    return await synthesize(tts_request)


@router.get("/health")
async def health():
    """检查 TTS 服务健康状态"""
    api_key = settings.TTS_API_KEY or settings.OPENAI_API_KEY
    if api_key:
        return {"status": "healthy", "service": "tts", "provider": "siliconflow"}
    return {"status": "unhealthy", "service": "tts", "error": "no api key"}
