"""技能管理 API

支持 Agent Skills 规范：
- /skills - 获取技能元数据列表（渐进加载）
- /skills/{id} - 获取技能完整内容
- /skills/{id}/stories - 故事管理（讲故事技能专用）
- /skills/{id}/stories/generate - 自动生成故事内容
"""

import os
import json
import aiofiles
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI
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


class StoryGenerateRequest(BaseModel):
    """生成故事请求"""
    title: str


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


async def crawl_story(title: str) -> str | None:
    """从七故事网搜索并爬取故事内容"""
    import httpx
    from bs4 import BeautifulSoup
    import urllib.parse
    import re

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            # 1. 先搜索故事
            search_url = f"https://www.qigushi.com/e/search/result/?searchid=1&q={urllib.parse.quote(title)}"
            print(f"[Crawl] 搜索: {search_url}")

            resp = await client.get(search_url, headers=headers)
            if resp.status_code != 200:
                print(f"[Crawl] 搜索失败: {resp.status_code}")
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 查找故事链接（支持所有分类）
            story_link = None
            story_categories = [
                'tonghuagushi',      # 童话故事
                'yuyangushi',        # 寓言故事
                'shuiqiangushi',     # 睡前故事
                'chengyugushi',      # 成语故事
                'youergushi',        # 幼儿故事
                'gudaigushi',        # 古代故事
                'zheligushi',        # 哲理故事
                'mingrengushi',      # 名人故事
                'aiguogushi',        # 爱国故事
                'yiqianlingyiye',    # 一千零一夜
                'antushengtonghua',  # 安徒生童话
                'gelintonghua',      # 格林童话
                'baobao',            # 宝宝睡前故事
            ]
            for a in soup.select('a[href*=".html"]'):
                href = a.get('href', '')
                text = a.get_text().strip()
                # 匹配包含故事标题的链接
                is_story_link = any(f'/{cat}/' in href for cat in story_categories)
                if title in text and is_story_link:
                    story_link = href
                    if not story_link.startswith('http'):
                        story_link = f"https://www.qigushi.com{story_link}"
                    print(f"[Crawl] 找到故事: {text} -> {story_link}")
                    break

            # 如果搜索没找到，尝试热门分类页面
            if not story_link:
                print(f"[Crawl] 搜索无结果，尝试分类页面")
                categories = [
                    ('yuyangushi', '寓言故事'),
                    ('tonghuagushi', '童话故事'),
                    ('chengyugushi', '成语故事'),
                    ('gelintonghua', '格林童话'),
                    ('antushengtonghua', '安徒生童话'),
                ]
                for cat_path, cat_name in categories:
                    try:
                        list_url = f"https://www.qigushi.com/{cat_path}/"
                        resp = await client.get(list_url, headers=headers)
                        soup = BeautifulSoup(resp.text, 'html.parser')

                        for a in soup.select(f'a[href*="/{cat_path}/"]'):
                            text = a.get_text().strip()
                            if title in text:
                                story_link = a.get('href')
                                if not story_link.startswith('http'):
                                    story_link = f"https://www.qigushi.com{story_link}"
                                print(f"[Crawl] {cat_name}找到: {text} -> {story_link}")
                                break
                        if story_link:
                            break
                    except:
                        continue

            if not story_link:
                print(f"[Crawl] 未找到故事: {title}")
                return None

            # 2. 爬取故事详情
            resp = await client.get(story_link, headers=headers)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 提取正文
            content_div = soup.select_one('.article-content') or soup.select_one('article')
            if not content_div:
                # 尝试获取所有 p 标签
                paragraphs = soup.select('p')
            else:
                paragraphs = content_div.select('p')

            if not paragraphs:
                return None

            # 提取文本
            content_parts = []
            for p in paragraphs:
                text = p.get_text().strip()
                # 过滤广告和无关内容
                if text and len(text) > 10 and '广告' not in text and '版权' not in text:
                    content_parts.append(text)

            if content_parts:
                content = '\n\n'.join(content_parts)
                print(f"[Crawl] 成功爬取 {len(content)} 字符")
                return content

    except Exception as e:
        print(f"[Crawl] 爬取失败: {e}")

    return None


@router.post("/{skill_id}/stories/generate")
async def generate_story(skill_id: str, request: StoryGenerateRequest):
    """根据故事名自动生成故事内容（先尝试爬取，失败则用AI生成）"""
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="故事名不能为空")

    source = "ai"  # 内容来源

    # 1. 先尝试从七故事网爬取
    crawled_content = await crawl_story(title)

    if crawled_content and len(crawled_content) > 100:
        # 爬取成功，直接返回（不经过 AI 改写，节省 token）
        source = "crawl"
        return {"title": title, "content": crawled_content, "source": source}

    # 2. 爬取失败，用 LLM 直接生成
    source = "ai"
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )

    prompt = f"""请为小朋友写一个《{title}》的故事。

要求：
1. 语言简单易懂，适合3-8岁儿童
2. 故事有趣生动，有教育意义
3. 长度适中，约300-500字
4. 结尾加上"---"分隔线，然后写上"**故事启示：**"总结故事寓意

只输出故事正文内容，不要包含标题。"""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "你是一个专业的儿童故事作家，擅长创作适合小朋友的有趣故事。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=1500,
        )

        content = response.choices[0].message.content.strip()

        return {
            "title": title,
            "content": content,
            "source": source,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成故事失败: {str(e)}")
