"""儿歌播放 API

支持：
- /songs - 获取儿歌列表
- /songs/{song_id} - 获取歌曲信息
- /songs/audio/{filename} - 播放歌曲音频
- /songs/upload - 上传儿歌
- /songs/{song_id} DELETE - 删除儿歌
"""

import os
import json
import re
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()


def get_songs_root() -> str:
    """获取儿歌根目录"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills", "songs")


def load_songs_index() -> list:
    """加载歌曲索引"""
    index_file = os.path.join(get_songs_root(), "index.json")
    if not os.path.exists(index_file):
        return []

    with open(index_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("songs", [])


def save_songs_index(songs: list) -> None:
    """保存歌曲索引"""
    index_file = os.path.join(get_songs_root(), "index.json")
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump({"songs": songs}, f, ensure_ascii=False, indent=2)


class SongItem(BaseModel):
    """歌曲项"""
    id: str
    title: str
    title_en: str
    file: str
    keywords: list[str]


class SongListResponse(BaseModel):
    """歌曲列表响应"""
    songs: list[SongItem]


@router.get("", response_model=SongListResponse)
async def list_songs():
    """获取所有儿歌列表"""
    songs = load_songs_index()
    return {"songs": songs}


@router.get("/{song_id}")
async def get_song(song_id: str):
    """获取单个歌曲信息"""
    songs = load_songs_index()
    for song in songs:
        if song["id"] == song_id:
            return song
    raise HTTPException(status_code=404, detail="歌曲不存在")


@router.get("/audio/{filename}")
async def get_song_audio(filename: str):
    """获取歌曲音频文件"""
    audio_dir = os.path.join(get_songs_root(), "audio")
    file_path = os.path.join(audio_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")

    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename,
    )


def find_song_by_keyword(keyword: str) -> dict | None:
    """根据关键词查找歌曲"""
    songs = load_songs_index()
    keyword_lower = keyword.lower()

    for song in songs:
        # 精确匹配标题
        if keyword_lower == song["title"].lower() or keyword_lower == song["title_en"].lower():
            return song
        # 关键词匹配
        for kw in song["keywords"]:
            if keyword_lower in kw.lower() or kw.lower() in keyword_lower:
                return song

    return None


def get_random_song() -> dict | None:
    """随机获取一首歌曲"""
    import random
    songs = load_songs_index()
    if not songs:
        return None
    return random.choice(songs)


def sanitize_filename(filename: str) -> str:
    """清理文件名，只保留安全字符"""
    # 移除路径分隔符和特殊字符
    name = os.path.basename(filename)
    # 只保留字母、数字、中文、下划线、连字符、点
    name = re.sub(r'[^\w\u4e00-\u9fff\-.]', '_', name)
    return name


@router.post("/upload")
async def upload_song(
    file: UploadFile = File(...),
    title: str = Form(...),
    title_en: str = Form(""),
    keywords: str = Form(""),  # 逗号分隔
):
    """上传儿歌

    Args:
        file: MP3 音频文件
        title: 歌曲中文名
        title_en: 歌曲英文名（可选）
        keywords: 关键词，逗号分隔（可选）
    """
    # 检查文件类型
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.mp3', '.wav', '.ogg', '.m4a']:
        raise HTTPException(status_code=400, detail="只支持 MP3/WAV/OGG/M4A 格式")

    # 生成唯一 ID 和文件名
    song_id = str(uuid.uuid4())[:8]
    safe_filename = sanitize_filename(file.filename)
    # 用 ID 作为前缀避免重名
    final_filename = f"{song_id}_{safe_filename}"

    # 确保 audio 目录存在
    audio_dir = os.path.join(get_songs_root(), "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # 保存文件
    file_path = os.path.join(audio_dir, final_filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 解析关键词
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    # 默认添加标题作为关键词
    if title not in kw_list:
        kw_list.insert(0, title)

    # 添加到索引
    songs = load_songs_index()
    new_song = {
        "id": song_id,
        "title": title,
        "title_en": title_en or title,
        "file": final_filename,
        "keywords": kw_list,
    }
    songs.append(new_song)
    save_songs_index(songs)

    return new_song


@router.delete("/{song_id}")
async def delete_song(song_id: str):
    """删除儿歌"""
    songs = load_songs_index()

    # 查找歌曲
    song_to_delete = None
    for song in songs:
        if song["id"] == song_id:
            song_to_delete = song
            break

    if not song_to_delete:
        raise HTTPException(status_code=404, detail="歌曲不存在")

    # 删除音频文件
    audio_dir = os.path.join(get_songs_root(), "audio")
    file_path = os.path.join(audio_dir, song_to_delete["file"])
    if os.path.exists(file_path):
        os.remove(file_path)

    # 从索引中移除
    songs = [s for s in songs if s["id"] != song_id]
    save_songs_index(songs)

    return {"success": True, "message": f"已删除: {song_to_delete['title']}"}
