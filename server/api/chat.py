"""对话 API - SSE 流式响应

支持意图预识别，讲故事场景直接读取故事文件，不经过 LLM 后处理。
"""

import json
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from agent import get_agent
from agent.intent import detect_intent_with_cache, StoryIntent, ListStoriesIntent
from agent.tools import tell_story, list_stories

router = APIRouter()


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    history: list[ChatMessage] = []
    thread_id: str | None = None
    # LLM 参数
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    assistant_name: str | None = None  # 助手名字


def build_messages(message: str, history: list[ChatMessage]) -> list:
    """构建消息列表"""
    messages = []
    for msg in history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
    messages.append(HumanMessage(content=message))
    return messages


async def stream_story_direct(
    story_name: str | None = None,
    assistant_name: str = "小智",
) -> AsyncGenerator[str, None]:
    """
    直接流式返回故事内容（不经过 LLM）

    这样可以避免 LLM 总结或改写故事内容。
    """
    # 直接调用 tell_story 工具获取故事
    # 注意：tell_story 是 @tool 装饰的，需要用 .invoke() 调用
    story_content = tell_story.invoke({"story_name": story_name or ""})

    # 发送工具调用开始事件（用于前端显示）
    yield f"data: {json.dumps({'type': 'skill_start', 'name': 'tell_story', 'input': {'story_name': story_name}}, ensure_ascii=False)}\n\n"

    # 发送工具调用完成事件
    yield f"data: {json.dumps({'type': 'skill_end', 'name': 'tell_story', 'output': story_content[:200]}, ensure_ascii=False)}\n\n"

    # 流式输出故事内容（模拟逐字输出效果）
    # 为了更自然的流式体验，按段落输出
    # 按段落分割
    paragraphs = story_content.split('\n')
    for para in paragraphs:
        if para.strip():
            # 输出段落内容
            yield f"data: {json.dumps({'type': 'token', 'content': para}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.05)  # 小延迟，更自然
        # 输出换行
        yield f"data: {json.dumps({'type': 'token', 'content': chr(10)}, ensure_ascii=False)}\n\n"

    # 添加互动结尾
    ending = f"\n\n好听吗？还想听别的故事吗？"
    yield f"data: {json.dumps({'type': 'token', 'content': ending}, ensure_ascii=False)}\n\n"

    # 完成
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def stream_list_stories_direct() -> AsyncGenerator[str, None]:
    """
    直接流式返回故事列表（不经过 LLM）
    """
    # 调用 list_stories 工具
    stories_content = list_stories.invoke({})

    # 发送工具调用事件
    yield f"data: {json.dumps({'type': 'skill_start', 'name': 'list_stories', 'input': {}}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'skill_end', 'name': 'list_stories', 'output': stories_content[:200]}, ensure_ascii=False)}\n\n"

    # 输出内容
    yield f"data: {json.dumps({'type': 'token', 'content': stories_content}, ensure_ascii=False)}\n\n"

    # 添加引导
    ending = "\n\n想听哪个故事呀？告诉我故事名字就好！"
    yield f"data: {json.dumps({'type': 'token', 'content': ending}, ensure_ascii=False)}\n\n"

    # 完成
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def stream_agent_response(
    message: str,
    history: list[ChatMessage],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    assistant_name: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    流式生成 Agent 响应

    事件类型：
    - token: 文本 token
    - skill_start: 技能开始调用
    - skill_end: 技能调用完成
    - done: 响应完成
    - error: 发生错误
    """
    agent = get_agent(model=model, temperature=temperature, max_tokens=max_tokens, assistant_name=assistant_name)
    messages = build_messages(message, history)

    try:
        # 使用 astream_events 获取流式事件
        async for event in agent.astream_events(
            {"messages": messages},
            version="v2"
        ):
            event_type = event.get("event", "")
            event_data = event.get("data", {})

            # 处理不同类型的事件
            if event_type == "on_chat_model_stream":
                # LLM 生成的 token
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    # 过滤掉工具调用的 content（通常是空的或者是工具调用 JSON）
                    content = chunk.content
                    if isinstance(content, str) and content:
                        yield f"data: {json.dumps({'type': 'token', 'content': content}, ensure_ascii=False)}\n\n"

            elif event_type == "on_tool_start":
                # 工具开始调用
                tool_name = event.get("name", "unknown")
                tool_input = event_data.get("input", {})
                yield f"data: {json.dumps({'type': 'skill_start', 'name': tool_name, 'input': tool_input}, ensure_ascii=False)}\n\n"

            elif event_type == "on_tool_end":
                # 工具调用完成
                tool_name = event.get("name", "unknown")
                tool_output = event_data.get("output", "")
                yield f"data: {json.dumps({'type': 'skill_end', 'name': tool_name, 'output': str(tool_output)[:200]}, ensure_ascii=False)}\n\n"

        # 发送完成事件
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    SSE 流式对话接口

    流程：
    1. 先进行意图识别
    2. 如果是讲故事/查列表，直接读取文件返回（不经过 LLM 后处理）
    3. 其他情况走正常 Agent 流程

    返回 Server-Sent Events 流，包含：
    - token: 逐字输出的文本
    - skill_start: 技能开始调用的提示
    - skill_end: 技能调用完成的结果
    - done: 响应完成
    - error: 错误信息
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    # Step 1: 意图识别
    intent = await detect_intent_with_cache(request.message, model=request.model)
    print(f"[Chat] 意图识别结果: {intent}")

    # Step 2: 根据意图分流
    if isinstance(intent, StoryIntent):
        # 讲故事：直接读取故事文件，不经过 LLM
        print(f"[Chat] 直接讲故事: {intent.story_name or '随机'}")
        return StreamingResponse(
            stream_story_direct(
                story_name=intent.story_name,
                assistant_name=request.assistant_name or "小智",
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    if isinstance(intent, ListStoriesIntent):
        # 查故事列表：直接返回列表
        print("[Chat] 直接返回故事列表")
        return StreamingResponse(
            stream_list_stories_direct(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    # Step 3: 其他意图，走正常 Agent 流程
    print("[Chat] 走 Agent 流程")
    return StreamingResponse(
        stream_agent_response(
            request.message,
            request.history,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            assistant_name=request.assistant_name,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/chat/simple")
async def chat_simple(request: ChatRequest):
    """
    简单对话接口（非流式）

    用于测试或不需要流式响应的场景
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    agent = get_agent(
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    messages = build_messages(request.message, request.history)

    try:
        result = await agent.ainvoke({"messages": messages})
        # 从结果中提取最后一条 AI 消息
        ai_messages = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
        response = ai_messages[-1].content if ai_messages else ""
        return {
            "success": True,
            "response": response,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
