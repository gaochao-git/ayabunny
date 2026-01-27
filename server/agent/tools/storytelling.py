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


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 Markdown frontmatter

    返回: (frontmatter字典, 正文内容)
    """
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            import yaml
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return frontmatter, body
            except:
                pass
    return {}, content


def load_story(story_id: str) -> dict | None:
    """加载单个故事"""
    stories_dir = get_stories_dir()
    file_path = os.path.join(stories_dir, f"{story_id}.md")

    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 解析 frontmatter
    frontmatter, body = parse_frontmatter(content)

    # 解析标题
    title = story_id
    for line in body.split("\n"):
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return {
        "id": story_id,
        "title": title,
        "content": body,
        "bgm": frontmatter.get("bgm"),  # 背景音乐
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
    """从故事库读取并讲述一个故事。这是唯一获取故事内容的方式！

    **重要**：你没有故事内容，必须调用此工具才能获取故事！禁止自己编写故事！

    **必须调用此工具的场景**：
    - 用户说"讲个故事"、"讲故事"、"想听故事"
    - 用户说"睡前故事"、"童话故事"
    - 用户提到具体故事名，如"讲小红帽"、"三只小猪的故事"
    - 用户从故事列表中选择了某个故事

    Args:
        story_name: 故事名称（可选）。不指定则随机讲一个故事。

    Returns:
        故事的完整内容，直接输出给用户即可。
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
    """列出所有可用的故事。

    **必须调用此工具的场景**：
    - 用户说"有哪些故事"、"故事列表"
    - 用户说"都有什么故事"、"可以讲什么故事"

    Returns:
        故事列表，直接告诉用户即可。
    """
    story_ids = get_all_story_ids()

    if not story_ids:
        return "目前没有可用的故事。"

    stories_info = []
    for idx, story_id in enumerate(story_ids, 1):
        story = load_story(story_id)
        if story:
            stories_info.append(story['title'])

    # 用顿号分隔，更适合语音朗读
    return f"目前有以下故事可以听：{' 、'.join(stories_info)}。"
