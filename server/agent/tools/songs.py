"""儿歌播放工具

支持播放、暂停、继续、停止、下一首等控制。
"""

import os
import json
import random
from langchain_core.tools import tool


def get_songs_dir() -> str:
    """获取儿歌目录路径"""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "skills",
        "songs"
    )


def load_songs_index() -> list[dict]:
    """加载歌曲索引"""
    index_file = os.path.join(get_songs_dir(), "index.json")
    if not os.path.exists(index_file):
        return []

    with open(index_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("songs", [])


def find_song_by_name(name: str) -> dict | None:
    """根据名称查找歌曲"""
    songs = load_songs_index()
    name_lower = name.lower()

    for song in songs:
        # 精确匹配标题
        if name_lower == song["title"].lower() or name_lower == song.get("title_en", "").lower():
            return song
        # 关键词匹配
        for kw in song.get("keywords", []):
            if name_lower in kw.lower() or kw.lower() in name_lower:
                return song

    return None


def get_random_song() -> dict | None:
    """随机获取一首歌曲"""
    songs = load_songs_index()
    if not songs:
        return None
    return random.choice(songs)


@tool
def play_song(song_name: str = "") -> str:
    """播放儿歌。当用户想听儿歌时调用此工具。

    **必须调用此工具的场景**：
    - 用户说"唱首儿歌"、"播放儿歌"、"听儿歌"
    - 用户说"唱歌"、"放首歌"、"播放歌曲"
    - 用户指定歌名，如"播放小星星"、"唱两只老虎"

    Args:
        song_name: 歌曲名称（可选）。不指定则随机播放。

    Returns:
        播放结果信息，包含歌曲信息供前端处理。
    """
    if song_name:
        song = find_song_by_name(song_name)
        if not song:
            # 没找到指定歌曲，随机播放
            song = get_random_song()
            if song:
                return json.dumps({
                    "action": "play",
                    "song": song,
                    "message": f"没找到《{song_name}》，我给你放一首《{song['title']}》吧！"
                }, ensure_ascii=False)
    else:
        song = get_random_song()

    if not song:
        return json.dumps({
            "action": "none",
            "message": "抱歉，目前没有可播放的儿歌。"
        }, ensure_ascii=False)

    return json.dumps({
        "action": "play",
        "song": song,
        "message": f"好的，现在播放《{song['title']}》！"
    }, ensure_ascii=False)


@tool
def pause_song() -> str:
    """暂停儿歌播放。当用户想暂停正在播放的儿歌时调用。

    **必须调用此工具的场景**：
    - 用户说"暂停"、"停一下"、"等一下"
    - 用户说"别唱了"、"先停下"

    Returns:
        暂停指令，供前端处理。
    """
    return json.dumps({
        "action": "pause",
        "message": "好的，已暂停播放。"
    }, ensure_ascii=False)


@tool
def resume_song() -> str:
    """继续播放儿歌。当用户想继续播放暂停的儿歌时调用。

    **必须调用此工具的场景**：
    - 用户说"继续"、"继续播放"、"接着放"
    - 用户说"继续唱"

    Returns:
        继续播放指令，供前端处理。
    """
    return json.dumps({
        "action": "resume",
        "message": "好的，继续播放。"
    }, ensure_ascii=False)


@tool
def stop_song() -> str:
    """停止儿歌播放。当用户想完全停止播放时调用。

    **必须调用此工具的场景**：
    - 用户说"停止"、"不听了"、"关掉"
    - 用户说"停止播放"、"不要了"

    Returns:
        停止指令，供前端处理。
    """
    return json.dumps({
        "action": "stop",
        "message": "好的，已停止播放。"
    }, ensure_ascii=False)


@tool
def next_song() -> str:
    """播放下一首儿歌。当用户想换一首歌时调用。

    **必须调用此工具的场景**：
    - 用户说"下一首"、"换一首"、"换个歌"
    - 用户说"不好听，换一个"

    Returns:
        下一首指令，供前端处理。
    """
    song = get_random_song()
    if not song:
        return json.dumps({
            "action": "none",
            "message": "抱歉，目前没有更多儿歌了。"
        }, ensure_ascii=False)

    return json.dumps({
        "action": "next",
        "song": song,
        "message": f"好的，换一首《{song['title']}》！"
    }, ensure_ascii=False)


@tool
def list_songs() -> str:
    """列出所有可用的儿歌。

    **必须调用此工具的场景**：
    - 用户说"有什么儿歌"、"儿歌列表"
    - 用户说"有哪些歌"、"能唱什么歌"

    Returns:
        儿歌列表。
    """
    songs = load_songs_index()

    if not songs:
        return "目前没有可用的儿歌。"

    titles = [song["title"] for song in songs]
    return f"目前有以下儿歌可以听：{'、'.join(titles)}。想听哪首？"
