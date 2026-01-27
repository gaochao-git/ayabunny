"""背景音乐管理 API

支持：
- /bgm - 获取 BGM 列表（预设 + 用户上传）
- /bgm/upload - 上传自定义 BGM
- /bgm/{filename} - 删除 BGM
"""

import os
import uuid
import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

router = APIRouter()

# BGM 存储目录
def get_bgm_root() -> str:
    """获取 BGM 根目录"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "bgm")


# 预设 BGM 列表
PRESET_BGM = [
    {"id": "sweet-dreams.mp3", "name": "甜蜜的梦", "preset": True},
    {"id": "moon-and-sun.mp3", "name": "月亮和太阳", "preset": True},
    {"id": "cotton-clouds.mp3", "name": "棉花云", "preset": True},
    {"id": "twinkle-star.mp3", "name": "小星星", "preset": True},
    {"id": "candy-town.mp3", "name": "糖果镇", "preset": True},
    {"id": "a-day-to-remember.mp3", "name": "值得纪念的一天", "preset": True},
    {"id": "story-gentle.mp3", "name": "轻柔故事", "preset": True},
]


class BGMItem(BaseModel):
    """BGM 项"""
    id: str           # 文件名
    name: str         # 显示名称
    preset: bool      # 是否预设


@router.get("")
async def list_bgm():
    """获取所有 BGM 列表（预设 + 用户上传）"""
    bgm_list = list(PRESET_BGM)  # 复制预设列表

    # 扫描用户上传的 BGM
    bgm_root = get_bgm_root()
    custom_dir = os.path.join(bgm_root, "custom")

    if os.path.exists(custom_dir):
        for filename in os.listdir(custom_dir):
            if filename.endswith((".mp3", ".wav", ".ogg", ".m4a")):
                # 从文件名生成显示名称
                name = os.path.splitext(filename)[0]
                # 如果有元数据文件，读取名称
                meta_file = os.path.join(custom_dir, f"{filename}.json")
                if os.path.exists(meta_file):
                    import json
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            name = meta.get("name", name)
                    except:
                        pass

                bgm_list.append({
                    "id": f"custom/{filename}",
                    "name": f"🎵 {name}",
                    "preset": False,
                })

    return {"bgm": bgm_list}


@router.post("/upload")
async def upload_bgm(
    file: UploadFile = File(...),
    name: str | None = None,
):
    """上传自定义 BGM"""
    # 验证文件类型
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".mp3", ".wav", ".ogg", ".m4a"]:
        raise HTTPException(status_code=400, detail="只支持 mp3, wav, ogg, m4a 格式")

    # 验证文件大小（最大 10MB）
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    # 生成唯一文件名
    unique_id = str(uuid.uuid4())[:8]
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._-")
    filename = f"{unique_id}_{safe_name}"

    # 保存文件
    bgm_root = get_bgm_root()
    custom_dir = os.path.join(bgm_root, "custom")
    os.makedirs(custom_dir, exist_ok=True)

    file_path = os.path.join(custom_dir, filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # 保存元数据（如果提供了自定义名称）
    display_name = name or os.path.splitext(file.filename)[0]
    meta_file = os.path.join(custom_dir, f"{filename}.json")
    import json
    async with aiofiles.open(meta_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps({"name": display_name}, ensure_ascii=False))

    return {
        "id": f"custom/{filename}",
        "name": f"🎵 {display_name}",
        "preset": False,
    }


@router.delete("/{filename:path}")
async def delete_bgm(filename: str):
    """删除自定义 BGM"""
    # 不允许删除预设 BGM
    if not filename.startswith("custom/"):
        raise HTTPException(status_code=403, detail="不能删除预设 BGM")

    bgm_root = get_bgm_root()
    file_path = os.path.join(bgm_root, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="BGM 不存在")

    # 删除文件
    os.remove(file_path)

    # 删除元数据
    meta_file = f"{file_path}.json"
    if os.path.exists(meta_file):
        os.remove(meta_file)

    return {"success": True, "message": "BGM 已删除"}
