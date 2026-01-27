"""古诗词朗诵工具

配合 Agent Skills 规范使用，属于 poetry 技能。
"""

import os
import random
from langchain_core.tools import tool


def get_poems_dir() -> str:
    """获取古诗目录路径"""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "skills",
        "poetry",
        "poems"
    )


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 Markdown frontmatter"""
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


def load_poem(poem_id: str) -> dict | None:
    """加载单首古诗"""
    poems_dir = get_poems_dir()
    file_path = os.path.join(poems_dir, f"{poem_id}.md")

    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter, body = parse_frontmatter(content)

    # 解析标题
    title = poem_id
    for line in body.split("\n"):
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return {
        "id": poem_id,
        "title": title,
        "content": body,
        "bgm": frontmatter.get("bgm"),
    }


def get_all_poem_ids() -> list[str]:
    """获取所有古诗 ID"""
    poems_dir = get_poems_dir()
    if not os.path.exists(poems_dir):
        return []

    return [
        filename[:-3]
        for filename in os.listdir(poems_dir)
        if filename.endswith(".md")
    ]


@tool
def recite_poem(poem_name: str = "") -> str:
    """朗诵一首古诗词。这是唯一获取古诗内容的方式！

    **重要**：你没有古诗内容，必须调用此工具才能获取！禁止自己编写！

    **必须调用此工具的场景**：
    - 用户说"背首古诗"、"念首诗"、"朗诵古诗"
    - 用户说"唐诗"、"宋词"、"古诗词"
    - 用户提到具体诗名，如"静夜思"、"春晓"
    - 用户从古诗列表中选择了某首诗

    Args:
        poem_name: 古诗名称（可选）。不指定则随机朗诵一首。

    Returns:
        古诗的完整内容，直接输出给用户即可。
    """
    poem_ids = get_all_poem_ids()

    if not poem_ids:
        return "抱歉，目前没有可用的古诗。请先添加一些古诗到诗词库中。"

    # 如果指定了诗名，尝试匹配
    if poem_name:
        # 直接匹配 ID
        if poem_name in poem_ids:
            poem = load_poem(poem_name)
            if poem:
                return f"好的，我来为你朗诵《{poem['title']}》：\n\n{poem['content']}"

        # 模糊匹配标题
        for poem_id in poem_ids:
            poem = load_poem(poem_id)
            if poem and poem_name.lower() in poem["title"].lower():
                return f"好的，我来为你朗诵《{poem['title']}》：\n\n{poem['content']}"

        # 没找到匹配的古诗
        available = ", ".join(poem_ids[:5])
        return f"抱歉，没有找到名为「{poem_name}」的古诗。可用的古诗有：{available}..."

    # 随机选择一首
    poem_id = random.choice(poem_ids)
    poem = load_poem(poem_id)

    if poem:
        return f"好的，我来为你朗诵《{poem['title']}》：\n\n{poem['content']}"

    return "抱歉，加载古诗时出现了问题。"


@tool
def list_poems() -> str:
    """列出所有可用的古诗词。

    **必须调用此工具的场景**：
    - 用户说"有哪些古诗"、"古诗列表"
    - 用户说"都有什么诗"、"可以背什么诗"
    - 用户想要选择一首古诗

    Returns:
        所有可用古诗的列表。
    """
    poem_ids = get_all_poem_ids()

    if not poem_ids:
        return "目前还没有古诗，请先添加一些古诗到诗词库中。"

    poems = []
    for poem_id in poem_ids:
        poem = load_poem(poem_id)
        if poem:
            poems.append(f"- {poem['title']}")

    return f"我会背诵以下古诗：\n\n" + "\n".join(poems) + "\n\n想听哪一首呢？"
