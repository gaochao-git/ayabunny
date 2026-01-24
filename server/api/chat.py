"""对话 API - SSE 流式响应"""

import json
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from agent import get_agent

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


async def stream_agent_response(
    message: str,
    history: list[ChatMessage]
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
    agent = get_agent()
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

    返回 Server-Sent Events 流，包含：
    - token: 逐字输出的文本
    - skill_start: 技能开始调用的提示
    - skill_end: 技能调用完成的结果
    - done: 响应完成
    - error: 错误信息
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    return StreamingResponse(
        stream_agent_response(request.message, request.history),
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

    agent = get_agent()
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
