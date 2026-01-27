"""意图识别模块

用轻量 LLM 调用判断用户意图，提取关键信息。
用于在 Agent 之前预处理，实现故事直接读取等优化。
"""

import json
import re
from typing import Literal
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from config import get_settings

settings = get_settings()


class StoryIntent(BaseModel):
    """讲故事意图"""
    intent: Literal["tell_story"]
    story_name: str | None = None  # 用户指定的故事名，None 表示随机


class ListStoriesIntent(BaseModel):
    """查询故事列表意图"""
    intent: Literal["list_stories"]


class PlaySongIntent(BaseModel):
    """播放儿歌意图"""
    intent: Literal["play_song"]
    song_name: str | None = None  # 用户指定的歌曲名，None 表示随机


class PauseSongIntent(BaseModel):
    """暂停儿歌意图"""
    intent: Literal["pause_song"]


class ResumeSongIntent(BaseModel):
    """继续播放意图"""
    intent: Literal["resume_song"]


class StopSongIntent(BaseModel):
    """停止播放意图"""
    intent: Literal["stop_song"]


class NextSongIntent(BaseModel):
    """下一首意图"""
    intent: Literal["next_song"]


class ListSongsIntent(BaseModel):
    """查询儿歌列表意图"""
    intent: Literal["list_songs"]


class ChatIntent(BaseModel):
    """普通对话意图"""
    intent: Literal["chat"]


# 意图联合类型
Intent = StoryIntent | ListStoriesIntent | PlaySongIntent | PauseSongIntent | ResumeSongIntent | StopSongIntent | NextSongIntent | ListSongsIntent | ChatIntent


# 意图识别 prompt（注意：大括号需要双写以避免被 .format() 解释）
INTENT_PROMPT = """你是一个意图识别助手。分析用户输入，判断用户意图。

## 意图类型

1. **tell_story** - 用户想听故事
   - "讲个故事"、"讲故事"、"想听故事"
   - "睡前故事"、"童话故事"
   - "讲小红帽"、"我想听曹冲称象"、"给我讲三只小猪的故事"
   - "再讲一个"、"换个故事"、"下一个故事"

2. **list_stories** - 用户想知道有哪些故事
   - "有什么故事"、"有哪些故事"
   - "故事列表"、"都有什么故事"

3. **play_song** - 用户想听儿歌
   - "唱首儿歌"、"播放儿歌"、"听儿歌"
   - "唱歌"、"放首歌"、"播放歌曲"
   - "播放小星星"、"唱两只老虎"

4. **pause_song** - 用户想暂停儿歌
   - "暂停"、"停一下"、"等一下"
   - "别唱了"、"先停下"

5. **resume_song** - 用户想继续播放
   - "继续"、"继续播放"、"接着放"
   - "继续唱"

6. **stop_song** - 用户想停止播放
   - "停止"、"不听了"、"关掉"
   - "停止播放"、"不要了"

7. **next_song** - 用户想换一首
   - "下一首"、"换一首"、"换个歌"
   - "不好听，换一个"

8. **list_songs** - 用户想知道有哪些儿歌
   - "有什么儿歌"、"儿歌列表"
   - "有哪些歌"、"能唱什么歌"

9. **chat** - 其他普通对话
   - 问问题、闲聊、其他非故事/儿歌相关的内容

## 输出格式

返回 JSON，格式如下：
- 讲故事：{{"intent": "tell_story", "story_name": "故事名或null"}}
- 查故事列表：{{"intent": "list_stories"}}
- 播放儿歌：{{"intent": "play_song", "song_name": "歌曲名或null"}}
- 暂停儿歌：{{"intent": "pause_song"}}
- 继续播放：{{"intent": "resume_song"}}
- 停止播放：{{"intent": "stop_song"}}
- 下一首：{{"intent": "next_song"}}
- 查儿歌列表：{{"intent": "list_songs"}}
- 普通对话：{{"intent": "chat"}}

## 注意
- story_name/song_name 只提取用户明确提到的名称，如果没指定，则为 null
- 只返回 JSON，不要有其他内容

用户输入：{user_input}
"""


def parse_intent_response(response: str) -> Intent:
    """解析 LLM 返回的意图 JSON"""
    try:
        # 尝试提取 JSON
        # 可能返回 ```json ... ``` 格式
        json_match = re.search(r'\{[^{}]+\}', response)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response)

        intent_type = data.get("intent", "chat")

        if intent_type == "tell_story":
            return StoryIntent(
                intent="tell_story",
                story_name=data.get("story_name")
            )
        elif intent_type == "list_stories":
            return ListStoriesIntent(intent="list_stories")
        elif intent_type == "play_song":
            return PlaySongIntent(
                intent="play_song",
                song_name=data.get("song_name")
            )
        elif intent_type == "pause_song":
            return PauseSongIntent(intent="pause_song")
        elif intent_type == "resume_song":
            return ResumeSongIntent(intent="resume_song")
        elif intent_type == "stop_song":
            return StopSongIntent(intent="stop_song")
        elif intent_type == "next_song":
            return NextSongIntent(intent="next_song")
        elif intent_type == "list_songs":
            return ListSongsIntent(intent="list_songs")
        else:
            return ChatIntent(intent="chat")

    except (json.JSONDecodeError, KeyError, ValueError):
        # 解析失败，默认为普通对话
        return ChatIntent(intent="chat")


async def detect_intent(
    user_input: str,
    model: str | None = None,
) -> Intent:
    """
    检测用户意图

    Args:
        user_input: 用户输入
        model: 模型名称（可选，使用更快的小模型）

    Returns:
        Intent 对象
    """
    # 使用轻量模型进行意图识别
    llm = ChatOpenAI(
        model=model or settings.OPENAI_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
        openai_api_base=settings.OPENAI_BASE_URL,
        temperature=0,  # 意图识别需要确定性
        max_tokens=100,  # 只需要返回简短 JSON
    )

    prompt = INTENT_PROMPT.format(user_input=user_input)

    try:
        response = await llm.ainvoke(prompt)
        return parse_intent_response(response.content)
    except Exception as e:
        print(f"[Intent] 意图识别失败: {e}")
        # 出错时默认为普通对话，让 Agent 处理
        return ChatIntent(intent="chat")


# 快速关键词预检（可选优化，减少 LLM 调用）
STORY_KEYWORDS = ["故事", "讲个", "讲一个", "想听", "睡前", "讲"]
LIST_KEYWORDS = ["有什么故事", "有哪些故事", "故事列表", "都有什么"]

# 儿歌相关关键词
SONG_KEYWORDS = ["儿歌", "唱歌", "放歌", "播放", "唱首", "放首"]
SONG_LIST_KEYWORDS = ["有什么儿歌", "有哪些歌", "儿歌列表", "能唱什么"]
PAUSE_KEYWORDS = ["暂停", "停一下", "等一下", "别唱了", "先停下"]
RESUME_KEYWORDS = ["继续", "继续播放", "接着放", "继续唱"]
STOP_KEYWORDS = ["停止", "不听了", "关掉", "停止播放", "不要了"]
NEXT_KEYWORDS = ["下一首", "换一首", "换个歌", "换一个"]

# 缓存已知故事名列表
_story_titles_cache: list[str] | None = None


def get_story_titles() -> list[str]:
    """获取所有故事标题（用于快速匹配）"""
    global _story_titles_cache
    if _story_titles_cache is None:
        try:
            from agent.tools.storytelling import get_all_story_ids, load_story
            story_ids = get_all_story_ids()
            _story_titles_cache = []
            for story_id in story_ids:
                story = load_story(story_id)
                if story:
                    _story_titles_cache.append(story['title'])
        except Exception:
            _story_titles_cache = []
    return _story_titles_cache


def match_story_name(user_input: str) -> str | None:
    """
    尝试从用户输入中匹配故事名

    Returns:
        匹配到的故事名，或 None
    """
    text = user_input.strip()
    titles = get_story_titles()

    for title in titles:
        # 完整匹配或包含匹配
        if title in text or text in title:
            return title

    return None


def quick_intent_check(user_input: str) -> tuple[str, str | None]:
    """
    快速关键词预检

    Returns:
        (intent_type, name)
        - ("tell_story", "故事名") - 直接匹配到故事
        - ("list_stories", None) - 查列表
        - ("play_song", "歌曲名") - 播放儿歌
        - ("pause_song", None) - 暂停
        - ("resume_song", None) - 继续
        - ("stop_song", None) - 停止
        - ("next_song", None) - 下一首
        - ("list_songs", None) - 儿歌列表
        - ("chat", None) - 普通对话
        - ("need_llm", None) - 需要 LLM 判断
    """
    text = user_input.strip()

    # 1. 检查儿歌控制命令（优先级最高，需要快速响应）
    for kw in PAUSE_KEYWORDS:
        if kw in text:
            return ("pause_song", None)

    for kw in RESUME_KEYWORDS:
        if kw in text:
            return ("resume_song", None)

    for kw in STOP_KEYWORDS:
        if kw in text:
            return ("stop_song", None)

    for kw in NEXT_KEYWORDS:
        if kw in text:
            return ("next_song", None)

    # 2. 检查是否是查儿歌列表
    for kw in SONG_LIST_KEYWORDS:
        if kw in text:
            return ("list_songs", None)

    # 3. 检查是否是查故事列表
    for kw in LIST_KEYWORDS:
        if kw in text:
            return ("list_stories", None)

    # 4. 检查是否包含儿歌关键词
    has_song_keyword = any(kw in text for kw in SONG_KEYWORDS)
    if has_song_keyword:
        # 包含儿歌关键词，需要 LLM 提取具体歌曲名
        return ("need_llm", None)

    # 5. 尝试直接匹配故事名（如用户直接说"白雪公主"）
    matched_story = match_story_name(text)
    if matched_story:
        return ("tell_story", matched_story)

    # 6. 检查是否包含故事关键词
    has_story_keyword = any(kw in text for kw in STORY_KEYWORDS)
    if has_story_keyword:
        # 包含故事关键词，需要 LLM 提取具体故事名
        return ("need_llm", None)

    # 7. 明显不是故事/儿歌相关
    return ("chat", None)


async def detect_intent_with_cache(
    user_input: str,
    model: str | None = None,
) -> Intent:
    """
    带快速预检的意图识别

    优先级：
    1. 儿歌控制命令（暂停、继续、停止、下一首）→ 立即返回
    2. 直接匹配故事名 → 立即返回 tell_story
    3. 查列表关键词 → 立即返回 list_stories/list_songs
    4. 包含故事/儿歌关键词 → 调用 LLM 提取名称
    5. 其他 → 返回 chat
    """
    # 快速预检
    intent_type, name = quick_intent_check(user_input)
    print(f"[Intent] 快速预检: type={intent_type}, name={name}")

    if intent_type == "tell_story":
        # 直接匹配到故事名
        return StoryIntent(intent="tell_story", story_name=name)

    if intent_type == "list_stories":
        return ListStoriesIntent(intent="list_stories")

    if intent_type == "play_song":
        return PlaySongIntent(intent="play_song", song_name=name)

    if intent_type == "pause_song":
        return PauseSongIntent(intent="pause_song")

    if intent_type == "resume_song":
        return ResumeSongIntent(intent="resume_song")

    if intent_type == "stop_song":
        return StopSongIntent(intent="stop_song")

    if intent_type == "next_song":
        return NextSongIntent(intent="next_song")

    if intent_type == "list_songs":
        return ListSongsIntent(intent="list_songs")

    if intent_type == "chat":
        return ChatIntent(intent="chat")

    # need_llm: 需要 LLM 判断和提取故事名/歌曲名
    return await detect_intent(user_input, model)
