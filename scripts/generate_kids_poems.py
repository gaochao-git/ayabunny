"""生成适合幼儿的古诗（带拼音和简单解释）"""

import os
from pypinyin import pinyin, Style

# 适合3-6岁幼儿的经典古诗（手动整理）
KIDS_POEMS = [
    {
        "title": "静夜思",
        "author": "李白",
        "content": "床前明月光，疑是地上霜。举头望明月，低头思故乡。",
        "explanation": "月亮的光照在床前，像是地上的白霜。抬头看看天上的月亮，低下头就想起了远方的家。"
    },
    {
        "title": "咏鹅",
        "author": "骆宾王",
        "content": "鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。",
        "explanation": "大白鹅弯着脖子对着天唱歌。雪白的羽毛漂在绿绿的水面上，红红的脚掌在清清的水里划呀划。"
    },
    {
        "title": "春晓",
        "author": "孟浩然",
        "content": "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。",
        "explanation": "春天睡觉太舒服了，不知不觉天就亮了。到处都能听到小鸟叽叽喳喳叫。昨晚下了雨刮了风，不知道小花掉了多少呀。"
    },
    {
        "title": "悯农",
        "author": "李绅",
        "content": "锄禾日当午，汗滴禾下土。谁知盘中餐，粒粒皆辛苦。",
        "explanation": "大中午农民伯伯在地里干活，汗水一滴一滴掉到土里。我们碗里的饭，每一粒都是辛辛苦苦种出来的，要珍惜粮食哦。"
    },
    {
        "title": "登鹳雀楼",
        "author": "王之涣",
        "content": "白日依山尽，黄河入海流。欲穷千里目，更上一层楼。",
        "explanation": "太阳靠着山落下去了，黄河的水流向大海。想看得更远吗？那就再爬高一层楼吧！"
    },
    {
        "title": "江雪",
        "author": "柳宗元",
        "content": "千山鸟飞绝，万径人踪灭。孤舟蓑笠翁，独钓寒江雪。",
        "explanation": "好多好多山，一只鸟都没有。好多好多路，一个人也看不到。只有一个老爷爷，穿着蓑衣戴着斗笠，一个人在下雪的江上钓鱼。"
    },
    {
        "title": "画",
        "author": "王维",
        "content": "远看山有色，近听水无声。春去花还在，人来鸟不惊。",
        "explanation": "这是一幅画呀！远远看山是彩色的，走近听水却没有声音。春天过去了花还在开，人走过来小鸟也不害怕飞走。"
    },
    {
        "title": "一去二三里",
        "author": "邵雍",
        "content": "一去二三里，烟村四五家。亭台六七座，八九十枝花。",
        "explanation": "走了二三里路，看到四五户人家冒着炊烟。路上有六七座小亭子，还有八九十朵漂亮的花。数字真好玩！"
    },
]


def add_pinyin_line(text):
    """给一行文字添加拼音（只给汉字加）"""
    result = []
    for char in text:
        if '\u4e00' <= char <= '\u9fff':  # 是汉字
            py = pinyin(char, style=Style.TONE)[0][0]
            result.append(f"{char}({py})")
        else:
            result.append(char)
    return ''.join(result)


def split_poem_lines(content):
    """把诗分成行"""
    lines = []
    current = ""
    for char in content:
        current += char
        if char in "。，！？":
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines


def generate_poem_file(poem, output_dir):
    """生成古诗 Markdown 文件"""
    title = poem["title"]
    author = poem["author"]
    content = poem["content"]
    explanation = poem["explanation"]

    lines = split_poem_lines(content)

    # 生成 Markdown
    md = f"""---
bgm: null
---

# {title}

{author}

"""
    for line in lines:
        md += f"{line}\n\n"

    md += f"---\n\n**讲给宝宝听**\n\n{explanation}\n"

    filepath = os.path.join(output_dir, f"{title}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"  {title}")


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

    print(f"生成 {len(KIDS_POEMS)} 首幼儿古诗...\n")

    for poem in KIDS_POEMS:
        generate_poem_file(poem, output_dir)

    print(f"\n完成！")


if __name__ == "__main__":
    main()
