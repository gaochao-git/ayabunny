"""技能管理 API

支持 Agent Skills 规范：
- /skills - 获取技能元数据列表（渐进加载）
- /skills/{id} - 获取技能完整内容
- /skills/{id}/stories - 故事管理（讲故事技能专用）
"""

import os
import json
import aiofiles
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import get_settings
from agent.skills_loader import (
    get_skill_registry,
    load_skill_content,
    discover_skills,
    SkillMetadata,
)

router = APIRouter()
settings = get_settings()

# 获取技能目录（从 skills_loader 模块）
def get_skills_root() -> str:
    """获取技能根目录"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")


class Story(BaseModel):
    """故事模型"""
    id: str
    title: str
    content: str
    category: str = "default"


class StoryCreate(BaseModel):
    """创建故事请求"""
    title: str
    content: str
    category: str = "default"


class StoryUpdate(BaseModel):
    """更新故事请求"""
    title: str | None = None
    content: str | None = None
    category: str | None = None


def get_skill_path(skill_id: str) -> str:
    """获取技能目录路径"""
    return os.path.join(get_skills_root(), skill_id)


def get_stories_path(skill_id: str) -> str:
    """获取故事目录路径"""
    return os.path.join(get_skill_path(skill_id), "stories")


@router.get("")
async def list_skills():
    """获取所有技能列表（只返回元数据，支持渐进加载）"""
    registry = get_skill_registry()
    skills = []
    for skill in registry.values():
        skills.append({
            "id": skill.id,
            "name": skill.name,
            "version": skill.version,
            "icon": skill.icon,
            "keywords": skill.keywords,
            "triggers": skill.triggers[:3] if skill.triggers else [],  # 只返回前3个触发条件
            "tools": skill.tools,
        })
    return {"skills": skills}


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """获取技能完整内容（按需加载）"""
    content = load_skill_content(skill_id)
    if not content:
        raise HTTPException(status_code=404, detail=f"技能 {skill_id} 不存在")

    return {
        "id": content.metadata.id,
        "name": content.metadata.name,
        "version": content.metadata.version,
        "icon": content.metadata.icon,
        "keywords": content.metadata.keywords,
        "triggers": content.metadata.triggers,
        "tools": content.metadata.tools,
        "content": content.full_content,
    }


@router.post("/reload")
async def reload_skills():
    """重新扫描并加载技能（开发调试用）"""
    skills = discover_skills()
    return {
        "message": "技能已重新加载",
        "count": len(skills),
        "skills": list(skills.keys()),
    }


@router.get("/{skill_id}/stories")
async def list_stories(skill_id: str):
    """获取技能的故事列表"""
    stories_path = get_stories_path(skill_id)
    if not os.path.exists(stories_path):
        return {"stories": []}

    stories = []
    for filename in os.listdir(stories_path):
        if filename.endswith(".md"):
            story_id = filename[:-3]
            file_path = os.path.join(stories_path, filename)
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                # 从 Markdown 中提取标题
                lines = content.split("\n")
                title = story_id
                for line in lines:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                stories.append({
                    "id": story_id,
                    "title": title,
                    "filename": filename
                })

    return {"stories": stories}


@router.get("/{skill_id}/stories/{story_id}")
async def get_story(skill_id: str, story_id: str):
    """获取故事详情"""
    file_path = os.path.join(get_stories_path(skill_id), f"{story_id}.md")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"故事 {story_id} 不存在")

    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        content = await f.read()

    # 解析 Markdown
    lines = content.split("\n")
    title = story_id
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return {
        "id": story_id,
        "title": title,
        "content": content
    }


@router.post("/{skill_id}/stories")
async def create_story(skill_id: str, story: StoryCreate):
    """创建新故事"""
    stories_path = get_stories_path(skill_id)
    os.makedirs(stories_path, exist_ok=True)

    # 生成 ID
    story_id = story.title.replace(" ", "_").lower()
    file_path = os.path.join(stories_path, f"{story_id}.md")

    if os.path.exists(file_path):
        raise HTTPException(status_code=409, detail=f"故事 {story_id} 已存在")

    # 创建 Markdown 内容
    content = f"# {story.title}\n\n{story.content}"

    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)

    return {
        "id": story_id,
        "title": story.title,
        "content": content
    }


@router.put("/{skill_id}/stories/{story_id}")
async def update_story(skill_id: str, story_id: str, story: StoryUpdate):
    """更新故事"""
    file_path = os.path.join(get_stories_path(skill_id), f"{story_id}.md")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"故事 {story_id} 不存在")

    # 读取现有内容
    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        existing_content = await f.read()

    # 解析现有标题
    lines = existing_content.split("\n")
    existing_title = story_id
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            existing_title = line[2:].strip()
            content_start = i + 1
            break

    # 更新内容
    new_title = story.title if story.title else existing_title
    if story.content:
        new_content = f"# {new_title}\n\n{story.content}"
    else:
        # 保留原有正文
        body = "\n".join(lines[content_start:]).strip()
        new_content = f"# {new_title}\n\n{body}"

    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(new_content)

    return {
        "id": story_id,
        "title": new_title,
        "content": new_content
    }


@router.delete("/{skill_id}/stories/{story_id}")
async def delete_story(skill_id: str, story_id: str):
    """删除故事"""
    file_path = os.path.join(get_stories_path(skill_id), f"{story_id}.md")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"故事 {story_id} 不存在")

    os.remove(file_path)
    return {"success": True, "message": f"故事 {story_id} 已删除"}
