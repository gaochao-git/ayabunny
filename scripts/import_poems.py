"""从 chinese-poetry 导入古诗到项目"""

import json
import os
import re
import requests

# 唐诗三百首 URL
TANG_300_URL = "https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/蒙学/tangshisanbaishou.json"

# 适合小朋友的经典古诗（五言绝句、七言绝句为主）
KIDS_POEMS = [
    "靜夜思", "静夜思",
    "春曉", "春晓",
    "登鸛雀樓", "登鹳雀楼",
    "憫農", "悯农",
    "詠鵝", "咏鹅",
    "江雪",
    "尋隱者不遇", "寻隐者不遇",
    "鹿柴",
    "竹裏館", "竹里馆",
    "送別", "送别", "山中送別",
    "相思",
    "雜詩", "杂诗",
    "鳥鳴澗", "鸟鸣涧",
    "山中",
    "秋浦歌",
    "獨坐敬亭山", "独坐敬亭山",
    "望廬山瀑布", "望庐山瀑布",
    "早發白帝城", "早发白帝城",
    "贈汪倫", "赠汪伦",
    "黃鶴樓送孟浩然之廣陵", "黄鹤楼送孟浩然之广陵",
    "望天門山", "望天门山",
    "絕句", "绝句",
    "楓橋夜泊", "枫桥夜泊",
    "遊子吟", "游子吟",
    "涼州詞", "凉州词",
    "出塞",
    "芙蓉樓送辛漸", "芙蓉楼送辛渐",
    "九月九日憶山東兄弟", "九月九日忆山东兄弟",
    "渭城曲",
    "送元二使安西",
    "宿建德江",
    "問劉十九",
    "八陣圖",
]


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


def is_kids_poem(title):
    """检查是否适合小朋友"""
    for kid_poem in KIDS_POEMS:
        if kid_poem in title or title in kid_poem:
            return True
    return False


def filter_kids_poems(poems):
    """筛选适合小朋友的古诗"""
    result = []
    seen_titles = set()

    for poem in poems:
        title = poem.get("chapter", "")
        if is_kids_poem(title):
            if title not in seen_titles:
                seen_titles.add(title)
                result.append(poem)

    return result


def sanitize_filename(title):
    """生成安全的文件名"""
    # 简单映射一些繁体字
    mapping = {
        "靜": "静", "曉": "晓", "鸛": "鹳", "樓": "楼",
        "裏": "里", "館": "馆", "詠": "咏", "鵝": "鹅",
        "廬": "庐", "發": "发", "陣": "阵", "圖": "图",
        "別": "别", "雜": "杂", "詩": "诗", "問": "问",
    }
    result = title
    for trad, simp in mapping.items():
        result = result.replace(trad, simp)

    # 移除不安全字符
    result = re.sub(r'[/\\:*?"<>|]', '', result)
    return result


def convert_to_markdown(poem, index):
    """转换为 Markdown 格式"""
    title = poem.get("chapter", f"无题{index}")
    author = poem.get("author", "佚名")
    paragraphs = poem.get("paragraphs", [])
    poem_type = poem.get("poem_type", "")

    # 生成文件名
    filename = sanitize_filename(title)

    # 生成内容
    content = f"""---
bgm: null
---

# {title}

**{poem_type}** · {author}

"""

    for para in paragraphs:
        # 清理注释标记
        clean_para = re.sub(r'\([^)]*一作[^)]*\)', '', para)
        clean_para = clean_para.strip()
        content += f"{clean_para}\n\n"

    return filename, content, title


def main():
    # 输出目录
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "server", "skills", "poetry", "stories"
    )
    os.makedirs(output_dir, exist_ok=True)

    # 下载数据
    data = download_poems()
    poems = extract_all_poems(data)
    print(f"共下载 {len(poems)} 首诗")

    # 筛选儿童诗
    kids_poems = filter_kids_poems(poems)
    print(f"筛选出 {len(kids_poems)} 首适合小朋友的诗")

    # 如果筛选太少，补充五言绝句
    if len(kids_poems) < 15:
        print("补充五言绝句...")
        seen = {p.get("chapter") for p in kids_poems}
        for poem in poems:
            if poem.get("poem_type") == "五言絕句" and poem.get("chapter") not in seen:
                kids_poems.append(poem)
                seen.add(poem.get("chapter"))
                if len(kids_poems) >= 30:
                    break

    # 转换并保存
    saved = []
    for i, poem in enumerate(kids_poems[:30], 1):  # 最多30首
        filename, content, title = convert_to_markdown(poem, i)
        filepath = os.path.join(output_dir, f"{filename}.md")

        # 跳过已存在的文件
        if os.path.exists(filepath):
            print(f"  跳过已存在: {title}")
            continue

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        saved.append((filename, title))
        print(f"  已保存: {title} -> {filename}.md")

    print(f"\n完成！共导入 {len(saved)} 首古诗到 {output_dir}")

    # 列出所有文件
    all_files = [f for f in os.listdir(output_dir) if f.endswith('.md')]
    print(f"\n目录中共有 {len(all_files)} 首古诗")


if __name__ == "__main__":
    main()
