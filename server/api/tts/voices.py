"""自定义音色管理"""

import os
import json
import uuid
import base64
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 自定义音色存储目录
VOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "voices")
os.makedirs(VOICES_DIR, exist_ok=True)

router = APIRouter()


class CustomVoice(BaseModel):
    """自定义音色"""
    id: str
    name: str
    description: str = ""
    created_at: str
    audio_file: str  # 音频文件名
    duration: float = 0  # 音频时长（秒）


class TestVoiceRequest(BaseModel):
    """测试音色请求"""
    text: str = "你好，这是一段测试语音。"


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


def get_voice_by_id(voice_id: str) -> dict | None:
    """根据 ID 获取音色"""
    voices = load_voices_index()
    return next((v for v in voices if v["id"] == voice_id), None)


def load_voice_audio_base64(voice: dict) -> str | None:
    """加载音色的参考音频（base64 编码）"""
    audio_path = os.path.join(VOICES_DIR, voice["audio_file"])
    if os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            audio_data = f.read()
            return base64.b64encode(audio_data).decode("utf-8")
    return None


def get_voice_mime_type(voice: dict) -> str:
    """获取音色文件的 MIME 类型"""
    audio_ext = voice["audio_file"].split(".")[-1].lower()
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "webm": "audio/webm",
    }.get(audio_ext, "audio/mpeg")


# ========== API 端点 ==========

@router.get("")
async def list_voices():
    """获取所有自定义音色列表"""
    voices = load_voices_index()
    return {"voices": voices}


@router.post("")
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


@router.delete("/{voice_id}")
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


@router.get("/{voice_id}/audio")
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
    media_type = get_voice_mime_type(voice)

    return FileResponse(audio_path, media_type=media_type)
