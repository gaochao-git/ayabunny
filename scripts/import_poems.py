"""从 chinese-poetry 导入小学必背古诗（简体版）"""

import os
import re
import requests
from opencc import OpenCC

# 繁体转简体
cc = OpenCC('t2s')

# 唐诗三百首 URL
TANG_300_URL = "https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/蒙学/tangshisanbaishou.json"

# 小学必背古诗（1-6年级教材）- 使用繁体和简体都列出方便匹配
XIAOXUE_POEMS = {
    # 一年级
    "靜夜思": "静夜思",
    "春曉": "春晓",
    "詠鵝": "咏鹅",
    "憫農": "悯农",
    # 二年级
    "登鸛雀樓": "登鹳雀楼",
    "望廬山瀑布": "望庐山瀑布",
    "贈汪倫": "赠汪伦",
    "江雪": "江雪",
    # 三年级
    "絕句": "绝句",
    "早發白帝城": "早发白帝城",
    "九月九日憶山東兄弟": "九月九日忆山东兄弟",
    "望天門山": "望天门山",
    # 四年级
    "鹿柴": "鹿柴",
    "送元二使安西": "送元二使安西",
    "渭城曲": "渭城曲",
    "楓橋夜泊": "枫桥夜泊",
    # 五年级
    "相思": "相思",
    "竹裏館": "竹里馆",
    "山中送別": "山中送别",
    "春夜喜雨": "春夜喜雨",
    # 六年级
    "出塞": "出塞",
    "涼州詞": "凉州词",
    "芙蓉樓送辛漸": "芙蓉楼送辛渐",
    "遊子吟": "游子吟",
}


def download_poems():
    """下载唐诗三百首"""
    print("下载唐诗三百首...")
    resp = requests.get(TANG_300_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_all_poems(data):
    """从嵌套结构中提取所有诗"""
    all_poems = []
    for section in data.get("content", []):
        poem_type = section.get("type", "")
        for poem in section.get("content", []):
            poem["poem_type"] = poem_type
            all_poems.append(poem)
    return all_poems


def is_xiaoxue_poem(title):
    """检查是否是小学必背古诗"""
    for trad_title in XIAOXUE_POEMS.keys():
        if trad_title in title or title in trad_title:
            return True
    return False


def to_simplified(text):
    """繁体转简体"""
    return cc.convert(text)


def sanitize_filename(title):
    """生成安全的文件名（简体）"""
    result = to_simplified(title)
    # 移除不安全字符
    result = re.sub(r'[/\\:*?"<>|·]', '', result)
    return result


def convert_to_markdown(poem):
    """转换为简体 Markdown 格式"""
    title = poem.get("chapter", "无题")
    author = poem.get("author", "佚名")
    paragraphs = poem.get("paragraphs", [])
    poem_type = poem.get("poem_type", "")

    # 转换为简体
    title_simp = to_simplified(title)
    author_simp = to_simplified(author)
    poem_type_simp = to_simplified(poem_type)

    # 生成文件名
    filename = sanitize_filename(title)

    # 生成内容
    content = f"""---
bgm: null
---

# {title_simp}

**{poem_type_simp}** · {author_simp}

"""

    for para in paragraphs:
        # 清理注释标记并转简体
        clean_para = re.sub(r'\([^)]*一作[^)]*\)', '', para)
        clean_para = to_simplified(clean_para.strip())
        content += f"{clean_para}\n\n"

    return filename, content, title_simp


def main():
    # 输出目录
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "server", "skills", "poetry", "poems"
    )
    os.makedirs(output_dir, exist_ok=True)

    # 清空现有古诗
    print("清空现有古诗...")
    for f in os.listdir(output_dir):
        if f.endswith('.md'):
            os.remove(os.path.join(output_dir, f))

    # 下载数据
    data = download_poems()
    poems = extract_all_poems(data)
    print(f"共下载 {len(poems)} 首诗")

    # 筛选小学必背古诗
    xiaoxue_poems = []
    seen_titles = set()

    for poem in poems:
        title = poem.get("chapter", "")
        if is_xiaoxue_poem(title):
            if title not in seen_titles:
                seen_titles.add(title)
                xiaoxue_poems.append(poem)

    print(f"筛选出 {len(xiaoxue_poems)} 首小学必背古诗")

    # 转换并保存
    saved = []
    for poem in xiaoxue_poems:
        filename, content, title = convert_to_markdown(poem)
        filepath = os.path.join(output_dir, f"{filename}.md")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        saved.append((filename, title))
        print(f"  已保存: {title} -> {filename}.md")

    print(f"\n完成！共导入 {len(saved)} 首小学必背古诗")
    print("\n古诗列表：")
    for _, title in saved:
        print(f"  - {title}")


if __name__ == "__main__":
    main()
