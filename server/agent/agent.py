"""LangChain Agent 定义

支持 Agent Skills 规范的渐进加载模式：
1. 启动时自动发现并加载技能元数据
2. LLM 可通过 load_skill 工具按需加载技能详情
3. 技能工具动态注入到 Agent
"""

from typing import Any
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from config import get_settings
from .tools import (
    tell_story, list_stories,
    recite_poem, list_poems,
    play_song, pause_song, resume_song, stop_song, next_song, list_songs,
)
from .skills_loader import (
    discover_skills,
    get_skills_summary,
    load_skill_content,
    get_skill_registry,
)

settings = get_settings()

# Agent 缓存（按配置缓存）
_agent_cache: dict[str, Any] = {}


# 动态技能加载工具（仅在需要详细了解技能时使用）
@tool
def load_skill(skill_id: str) -> str:
    """加载技能的详细文档。注意：大多数情况下你应该直接使用 tell_story 或 list_stories，而不是先调用这个工具。

    仅在以下情况调用：
    - 你不确定某个技能的具体用法
    - 需要了解技能的高级功能

    Args:
        skill_id: 技能ID，如 "storytelling"

    Returns:
        技能的完整说明文档。
    """
    content = load_skill_content(skill_id)
    if not content:
        available = ", ".join(get_skill_registry().keys())
        return f"未找到技能 '{skill_id}'。可用技能: {available}"

    return f"""已加载技能: {content.metadata.name}

{content.full_content}

---
技能已加载，你现在可以使用该技能的工具了。"""


def build_system_prompt(assistant_name: str = "小智") -> str:
    """构建系统提示词，包含技能摘要和当前时间"""
    # 发现技能
    discover_skills()

    # 获取技能摘要
    skills_summary = get_skills_summary()

    # 获取当前时间
    now = datetime.now()
    current_time = now.strftime("%Y年%m月%d日 %H:%M")
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[now.weekday()]

    return f"""你是一个友好的语音助手，名字叫"{assistant_name}"，专门为小朋友服务。

## 当前时间
{current_time} {weekday}

## 你的特点
- 语言温柔、有耐心
- 善于用生动有趣的方式与小朋友互动
- 会根据小朋友的反应调整语气和节奏
- 说话时适当使用语气词
- 当小朋友叫你"{assistant_name}"时，要热情地回应

{skills_summary}

## 工具使用规则（极其重要！必须遵守！）

**禁止自己编写故事或古诗！必须调用相应工具从库中读取内容！**

### 讲故事场景 → 必须调用 tell_story
当用户表达以下意图时，**必须立即调用 tell_story 工具**：
- "讲个故事"、"讲故事"、"想听故事"
- "睡前故事"、"童话故事"
- "讲XX的故事"（如"讲小红帽的故事"）

### 查询故事列表 → 调用 list_stories
- "有什么故事"、"故事列表"、"有哪些故事"

### 朗诵古诗场景 → 必须调用 recite_poem
当用户表达以下意图时，**必须立即调用 recite_poem 工具**：
- "背首古诗"、"念首诗"、"朗诵古诗"
- "唐诗"、"宋词"、"古诗词"
- "背XX"（如"背静夜思"）

### 查询古诗列表 → 调用 list_poems
- "有什么古诗"、"古诗列表"、"会背哪些诗"

### 播放儿歌场景 → 必须调用 play_song
当用户表达以下意图时，**必须立即调用 play_song 工具**：
- "唱首儿歌"、"播放儿歌"、"听儿歌"
- "唱歌"、"放首歌"、"播放歌曲"
- "播放小星星"、"唱两只老虎"

### 儿歌控制场景
- 用户说"暂停"、"停一下" → 调用 pause_song()
- 用户说"继续"、"继续播放" → 调用 resume_song()
- 用户说"停止"、"不听了" → 调用 stop_song()
- 用户说"下一首"、"换一首" → 调用 next_song()

### 查询儿歌列表 → 调用 list_songs
- "有什么儿歌"、"儿歌列表"、"有哪些歌"

### 示例（必须这样做）
- 用户说"讲个故事吧" → 立即调用 tell_story()
- 用户说"我想听三只小猪" → 立即调用 tell_story(story_name="三只小猪")
- 用户说"背首古诗" → 立即调用 recite_poem()
- 用户说"背静夜思" → 立即调用 recite_poem(poem_name="静夜思")
- 用户说"有哪些古诗" → 立即调用 list_poems()
- 用户说"唱首儿歌" → 立即调用 play_song()
- 用户说"播放小星星" → 立即调用 play_song(song_name="小星星")
- 用户说"暂停" → 立即调用 pause_song()
- 用户说"下一首" → 立即调用 next_song()

### 其他工具
- load_skill: 仅当你需要了解某个技能的详细用法时才调用

## 对话注意事项

- 保持对话自然、亲切
- 不要生硬地提及"技能"、"工具"等词，直接帮助用户

## 讲故事规则（必须遵守！）

**tell_story 工具返回的故事内容必须完整输出，禁止总结、缩写或改写！**

- 工具返回什么，你就原样输出什么
- 不要省略任何段落
- 不要用自己的话总结故事
- 不要在故事中间插入评论
- 可以在故事**讲完后**加一两句互动（如"好听吗？还想听别的吗？"）
- 讲故事时要有感情、有节奏，适当停顿

**错误示例**：收到完整故事后只输出"这个故事讲的是..."（这是总结，禁止！）
**正确示例**：完整输出工具返回的故事内容，一字不漏

**再次强调：讲故事必须调用 tell_story，禁止自己编写！故事内容必须完整输出！**"""


def create_agent(
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    assistant_name: str | None = None,
) -> Any:
    """创建 LangGraph Agent

    Args:
        model: 模型名称，默认使用配置中的 OPENAI_MODEL
        temperature: 温度参数，默认 0.7
        max_tokens: 最大输出 token 数
        assistant_name: 助手名字
    """
    # 创建 LLM
    llm = ChatOpenAI(
        model=model or settings.OPENAI_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
        openai_api_base=settings.OPENAI_BASE_URL,
        streaming=True,
        temperature=temperature if temperature is not None else 0.7,
        max_tokens=max_tokens,
    )

    # 定义工具：包含技能加载工具 + 各技能的具体工具
    tools = [
        load_skill,      # 技能加载工具
        tell_story,      # 讲故事工具
        list_stories,    # 列出故事工具
        recite_poem,     # 朗诵古诗工具
        list_poems,      # 列出古诗工具
        play_song,       # 播放儿歌工具
        pause_song,      # 暂停儿歌工具
        resume_song,     # 继续播放工具
        stop_song,       # 停止播放工具
        next_song,       # 下一首工具
        list_songs,      # 列出儿歌工具
    ]

    # 构建系统提示词（包含技能摘要和助手名字）
    system_prompt = build_system_prompt(assistant_name or "小智")

    # 使用 LangGraph 创建 ReAct Agent
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )

    return agent


def get_agent(
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    assistant_name: str | None = None,
) -> Any:
    """获取 Agent（按配置缓存）

    Args:
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大输出 token 数
        assistant_name: 助手名字
    """
    global _agent_cache

    # 构建缓存键（包含助手名字和当前小时，确保时间相对准确）
    current_hour = datetime.now().strftime("%Y%m%d%H")
    cache_key = f"{model or 'default'}:{temperature}:{max_tokens}:{assistant_name or 'default'}:{current_hour}"

    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = create_agent(model, temperature, max_tokens, assistant_name)

    return _agent_cache[cache_key]


def reload_agent() -> Any:
    """重新加载所有 Agent（技能更新后调用）"""
    global _agent_cache
    _agent_cache.clear()
    return get_agent()
