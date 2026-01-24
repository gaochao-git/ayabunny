"""LangChain Agent 定义

支持 Agent Skills 规范的渐进加载模式：
1. 启动时自动发现并加载技能元数据
2. LLM 可通过 load_skill 工具按需加载技能详情
3. 技能工具动态注入到 Agent
"""

from typing import Any
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


# 动态技能加载工具
@tool
def load_skill(skill_id: str) -> str:
    """加载指定技能的详细信息。当你需要了解某个技能的具体用法时调用此工具。

    Args:
        skill_id: 技能ID，如 "storytelling"

    Returns:
        技能的完整说明文档，包括触发条件、工具用法、对话风格等。
    """
    content = load_skill_content(skill_id)
    if not content:
        available = ", ".join(get_skill_registry().keys())
        return f"未找到技能 '{skill_id}'。可用技能: {available}"

    return f"""已加载技能: {content.metadata.name}

{content.full_content}

---
技能已加载，你现在可以使用该技能的工具了。"""


def build_system_prompt() -> str:
    """构建系统提示词，包含技能摘要"""
    # 发现技能
    discover_skills()

    # 获取技能摘要
    skills_summary = get_skills_summary()

    return f"""你是一个友好的语音助手，专门为小朋友服务。

你的特点：
- 语言温柔、有耐心
- 善于用生动有趣的方式与小朋友互动
- 会根据小朋友的反应调整语气和节奏
- 说话时适当使用语气词

{skills_summary}

## 使用技能

当用户的请求匹配某个技能的触发条件时：
1. 如果需要了解技能详情，使用 `load_skill` 工具加载技能文档
2. 使用技能提供的工具完成用户请求

## 对话注意事项

- 保持对话自然、亲切
- 不要生硬地提及"技能"这个词，直接帮助用户
- 如果不确定用户意图，可以友好地询问"""


def create_agent(
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Any:
    """创建 LangGraph Agent

    Args:
        model: 模型名称，默认使用配置中的 OPENAI_MODEL
        temperature: 温度参数，默认 0.7
        max_tokens: 最大输出 token 数
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

    # 构建系统提示词（包含技能摘要）
    system_prompt = build_system_prompt()

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
) -> Any:
    """获取 Agent（按配置缓存）

    Args:
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大输出 token 数
    """
    global _agent_cache

    # 构建缓存键
    cache_key = f"{model or 'default'}:{temperature}:{max_tokens}"

    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = create_agent(model, temperature, max_tokens)

    return _agent_cache[cache_key]


def reload_agent() -> Any:
    """重新加载所有 Agent（技能更新后调用）"""
    global _agent_cache
    _agent_cache.clear()
    return get_agent()
