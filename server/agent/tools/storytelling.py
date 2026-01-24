"""讲故事工具

配合 Agent Skills 规范使用，属于 storytelling 技能。
"""

import os
import random
from langchain_core.tools import tool


def get_stories_dir() -> str:
    """获取故事目录路径（从技能目录读取）"""
    # 技能目录在 server/skills/storytelling/stories
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "skills",
        "storytelling",
        "stories"
    )


def load_story(story_id: str) -> dict | None:
    """加载单个故事"""
    stories_dir = get_stories_dir()
    file_path = os.path.join(stories_dir, f"{story_id}.md")

    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

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


def get_all_story_ids() -> list[str]:
    """获取所有故事 ID"""
    stories_dir = get_stories_dir()
    if not os.path.exists(stories_dir):
        return []

    return [
        filename[:-3]
        for filename in os.listdir(stories_dir)
        if filename.endswith(".md")
    ]


@tool
def tell_story(story_name: str = "") -> str:
    """讲故事工具。当用户想听故事、讲故事时调用此工具。

    Args:
        story_name: 故事名称或ID（可选）。如不指定或为空字符串则随机选择一个故事。

    Returns:
        故事内容，包括标题和正文。如果找不到故事则返回提示信息。
    """
    story_ids = get_all_story_ids()

    if not story_ids:
        return "抱歉，目前没有可用的故事。请先添加一些故事到故事库中。"

    # 如果指定了故事名称，尝试匹配
    if story_name:
        # 直接匹配 ID
        if story_name in story_ids:
            story = load_story(story_name)
            if story:
                return f"好的，我来给你讲《{story['title']}》这个故事：\n\n{story['content']}"

        # 模糊匹配标题
        for story_id in story_ids:
            story = load_story(story_id)
            if story and story_name.lower() in story["title"].lower():
                return f"好的，我来给你讲《{story['title']}》这个故事：\n\n{story['content']}"

        # 没找到匹配的故事
        available = ", ".join(story_ids[:5])
        return f"抱歉，没有找到名为「{story_name}」的故事。可用的故事有：{available}..."

    # 随机选择一个故事
    story_id = random.choice(story_ids)
    story = load_story(story_id)

    if story:
        return f"好的，我来给你讲《{story['title']}》这个故事：\n\n{story['content']}"

    return "抱歉，加载故事时出现了问题。"


@tool
def list_stories() -> str:
    """列出所有可用的故事。当用户询问有哪些故事可以听时调用此工具。

    Returns:
        所有可用故事的列表。
    """
    story_ids = get_all_story_ids()

    if not story_ids:
        return "目前没有可用的故事。"

    stories_info = []
    for story_id in story_ids:
        story = load_story(story_id)
        if story:
            stories_info.append(f"- {story['title']}")

    return f"目前有以下故事可以听：\n" + "\n".join(stories_info)
