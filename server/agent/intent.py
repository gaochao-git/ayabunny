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


class ChatIntent(BaseModel):
    """普通对话意图"""
    intent: Literal["chat"]


# 意图联合类型
Intent = StoryIntent | ListStoriesIntent | ChatIntent


# 意图识别 prompt
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

3. **chat** - 其他普通对话
   - 问问题、闲聊、其他任何非故事相关的内容

## 输出格式

返回 JSON，格式如下：
- 讲故事：{"intent": "tell_story", "story_name": "故事名或null"}
- 查列表：{"intent": "list_stories"}
- 普通对话：{"intent": "chat"}

## 注意
- story_name 只提取用户明确提到的故事名，如果用户只说"讲个故事"没指定，则为 null
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
        (intent_type, story_name)
        - ("tell_story", "故事名") - 直接匹配到故事
        - ("list_stories", None) - 查列表
        - ("chat", None) - 普通对话
        - ("need_llm", None) - 需要 LLM 判断
    """
    text = user_input.strip()

    # 1. 检查是否是查列表
    for kw in LIST_KEYWORDS:
        if kw in text:
            return ("list_stories", None)

    # 2. 尝试直接匹配故事名（如用户直接说"白雪公主"）
    matched_story = match_story_name(text)
    if matched_story:
        return ("tell_story", matched_story)

    # 3. 检查是否包含故事关键词
    has_story_keyword = any(kw in text for kw in STORY_KEYWORDS)
    if has_story_keyword:
        # 包含故事关键词，需要 LLM 提取具体故事名
        return ("need_llm", None)

    # 4. 明显不是故事相关
    return ("chat", None)


async def detect_intent_with_cache(
    user_input: str,
    model: str | None = None,
) -> Intent:
    """
    带快速预检的意图识别

    优先级：
    1. 直接匹配故事名 → 立即返回 tell_story
    2. 查列表关键词 → 立即返回 list_stories
    3. 包含故事关键词 → 调用 LLM 提取故事名
    4. 其他 → 返回 chat
    """
    # 快速预检
    intent_type, story_name = quick_intent_check(user_input)
    print(f"[Intent] 快速预检: type={intent_type}, story={story_name}")

    if intent_type == "tell_story":
        # 直接匹配到故事名
        return StoryIntent(intent="tell_story", story_name=story_name)

    if intent_type == "list_stories":
        return ListStoriesIntent(intent="list_stories")

    if intent_type == "chat":
        return ChatIntent(intent="chat")

    # need_llm: 需要 LLM 判断和提取故事名
    return await detect_intent(user_input, model)
