"""导入幼儿启蒙古诗（适合3-6岁）"""

import os
import re
import requests
from opencc import OpenCC

cc = OpenCC('t2s')

TANG_300_URL = "https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/蒙学/tangshisanbaishou.json"

# 幼儿启蒙古诗（3-6岁，简单易懂）
YOUER_POEMS = [
    "靜夜思",   # 床前明月光
    "春曉",     # 春眠不觉晓
    "登鸛雀樓", # 白日依山尽
    "江雪",     # 千山鸟飞绝
    "相思",     # 红豆生南国
    "鹿柴",     # 空山不见人
]


def download_poems():
    print("下载唐诗三百首...")
    resp = requests.get(TANG_300_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_all_poems(data):
    all_poems = []
    for section in data.get("content", []):
        for poem in section.get("content", []):
            all_poems.append(poem)
    return all_poems


def is_youer_poem(title):
    """精确匹配，避免"相思"匹配到"长相思" """
    for t in YOUER_POEMS:
        if t == title or title == cc.convert(t):
            return True
    return False


def to_simplified(text):
    return cc.convert(text)


def sanitize_filename(title):
    result = to_simplified(title)
    result = re.sub(r'[/\\:*?"<>|·]', '', result)
    return result


def convert_to_markdown(poem):
    title = poem.get("chapter", "无题")
    author = poem.get("author", "佚名")
    paragraphs = poem.get("paragraphs", [])

    title_simp = to_simplified(title)
    author_simp = to_simplified(author)
    filename = sanitize_filename(title)

    # 简洁格式：标题 + 作者 + 诗句
    content = f"""---
bgm: null
---

# {title_simp}

{author_simp}

"""
    for para in paragraphs:
        clean_para = re.sub(r'\([^)]*一作[^)]*\)', '', para)
        clean_para = to_simplified(clean_para.strip())
        content += f"{clean_para}\n\n"

    return filename, content, title_simp


def main():
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "server", "skills", "poetry", "poems"
    )
    os.makedirs(output_dir, exist_ok=True)

    # 清空
    for f in os.listdir(output_dir):
        if f.endswith('.md'):
            os.remove(os.path.join(output_dir, f))

    data = download_poems()
    poems = extract_all_poems(data)
    print(f"共 {len(poems)} 首诗")

    # 筛选
    youer_poems = []
    seen = set()
    for poem in poems:
        title = poem.get("chapter", "")
        if is_youer_poem(title) and title not in seen:
            seen.add(title)
            youer_poems.append(poem)

    print(f"筛选出 {len(youer_poems)} 首幼儿启蒙古诗")

    # 保存
    for poem in youer_poems:
        filename, content, title = convert_to_markdown(poem)
        filepath = os.path.join(output_dir, f"{filename}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  {title}")

    print(f"\n完成！共 {len(youer_poems)} 首")


if __name__ == "__main__":
    main()
