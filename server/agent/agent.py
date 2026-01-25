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
from .tools import tell_story, list_stories
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

## 工具使用规则（重要！）

你必须根据用户意图**直接调用**对应的工具，不要犹豫：

### 讲故事场景 → 直接调用 tell_story
当用户表达以下意图时，**立即调用 tell_story 工具**：
- "讲个故事"、"讲故事"、"想听故事"
- "睡前故事"、"童话故事"
- "讲XX的故事"（如"讲小红帽的故事"）
- "有什么故事"、"故事列表" → 调用 list_stories

示例：
- 用户说"讲个故事吧" → 立即调用 tell_story()
- 用户说"我想听三只小猪" → 立即调用 tell_story(story_name="三只小猪")
- 用户说"有哪些故事" → 立即调用 list_stories()

### 其他工具
- load_skill: 仅当你需要了解某个技能的详细用法时才调用

## 对话注意事项

- 保持对话自然、亲切
- 不要生硬地提及"技能"、"工具"等词，直接帮助用户
- 工具返回的内容就是你要讲述的内容，直接输出给用户
- 讲故事时要有感情、有节奏，适当停顿"""


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
