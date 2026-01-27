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
from agent.intent import (
    detect_intent_with_cache,
    StoryIntent, ListStoriesIntent,
    PlaySongIntent, PauseSongIntent, ResumeSongIntent, StopSongIntent, NextSongIntent, ListSongsIntent,
)
from agent.tools import tell_story, list_stories
from agent.tools.songs import play_song, pause_song, resume_song, stop_song, next_song, list_songs as list_songs_tool

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
    from agent.tools.storytelling import load_story, get_all_story_ids
    import random

    # 获取故事及其 BGM 信息
    story_bgm = None
    story_ids = get_all_story_ids()

    if story_name and story_ids:
        # 尝试匹配故事
        for story_id in story_ids:
            story_data = load_story(story_id)
            if story_data:
                if story_id == story_name or (story_name.lower() in story_data["title"].lower()):
                    story_bgm = story_data.get("bgm")
                    break
    elif story_ids:
        # 随机选择故事
        story_id = random.choice(story_ids)
        story_data = load_story(story_id)
        if story_data:
            story_bgm = story_data.get("bgm")

    # 直接调用 tell_story 工具获取故事
    # 注意：tell_story 是 @tool 装饰的，需要用 .invoke() 调用
    story_content = tell_story.invoke({"story_name": story_name or ""})

    # 发送工具调用开始事件（用于前端显示，包含 bgm 信息）
    yield f"data: {json.dumps({'type': 'skill_start', 'name': 'tell_story', 'input': {'story_name': story_name}, 'bgm': story_bgm}, ensure_ascii=False)}\n\n"

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


async def stream_play_song_direct(song_name: str | None = None) -> AsyncGenerator[str, None]:
    """
    直接播放儿歌（不经过 LLM）
    """
    # 调用 play_song 工具
    result = play_song.invoke({"song_name": song_name or ""})
    data = json.loads(result)

    # 发送工具调用事件
    yield f"data: {json.dumps({'type': 'skill_start', 'name': 'play_song', 'input': {'song_name': song_name}}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'skill_end', 'name': 'play_song', 'output': data.get('message', '')[:200]}, ensure_ascii=False)}\n\n"

    # 发送音乐控制事件
    if data.get("action") == "play" and data.get("song"):
        yield f"data: {json.dumps({'type': 'music', 'action': 'play', 'song': data['song']}, ensure_ascii=False)}\n\n"

    # 输出消息
    yield f"data: {json.dumps({'type': 'token', 'content': data.get('message', '')}, ensure_ascii=False)}\n\n"

    # 完成
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def stream_pause_song_direct() -> AsyncGenerator[str, None]:
    """
    暂停儿歌播放
    """
    result = pause_song.invoke({})
    data = json.loads(result)

    # 发送音乐控制事件
    yield f"data: {json.dumps({'type': 'music', 'action': 'pause'}, ensure_ascii=False)}\n\n"

    # 输出消息
    yield f"data: {json.dumps({'type': 'token', 'content': data.get('message', '')}, ensure_ascii=False)}\n\n"

    # 完成
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def stream_resume_song_direct() -> AsyncGenerator[str, None]:
    """
    继续播放儿歌
    """
    result = resume_song.invoke({})
    data = json.loads(result)

    # 发送音乐控制事件
    yield f"data: {json.dumps({'type': 'music', 'action': 'resume'}, ensure_ascii=False)}\n\n"

    # 输出消息
    yield f"data: {json.dumps({'type': 'token', 'content': data.get('message', '')}, ensure_ascii=False)}\n\n"

    # 完成
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def stream_stop_song_direct() -> AsyncGenerator[str, None]:
    """
    停止播放儿歌
    """
    result = stop_song.invoke({})
    data = json.loads(result)

    # 发送音乐控制事件
    yield f"data: {json.dumps({'type': 'music', 'action': 'stop'}, ensure_ascii=False)}\n\n"

    # 输出消息
    yield f"data: {json.dumps({'type': 'token', 'content': data.get('message', '')}, ensure_ascii=False)}\n\n"

    # 完成
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def stream_next_song_direct() -> AsyncGenerator[str, None]:
    """
    播放下一首儿歌
    """
    result = next_song.invoke({})
    data = json.loads(result)

    # 发送音乐控制事件
    if data.get("action") == "next" and data.get("song"):
        yield f"data: {json.dumps({'type': 'music', 'action': 'next', 'song': data['song']}, ensure_ascii=False)}\n\n"

    # 输出消息
    yield f"data: {json.dumps({'type': 'token', 'content': data.get('message', '')}, ensure_ascii=False)}\n\n"

    # 完成
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def stream_list_songs_direct() -> AsyncGenerator[str, None]:
    """
    直接返回儿歌列表（不经过 LLM）
    """
    # 调用 list_songs 工具
    songs_content = list_songs_tool.invoke({})

    # 发送工具调用事件
    yield f"data: {json.dumps({'type': 'skill_start', 'name': 'list_songs', 'input': {}}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'skill_end', 'name': 'list_songs', 'output': songs_content[:200]}, ensure_ascii=False)}\n\n"

    # 输出内容
    yield f"data: {json.dumps({'type': 'token', 'content': songs_content}, ensure_ascii=False)}\n\n"

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
    - music: 音乐控制事件
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

                # 提取实际的输出内容（可能是对象或字符串）
                output_str = ""
                if hasattr(tool_output, "content"):
                    output_str = tool_output.content
                elif isinstance(tool_output, str):
                    output_str = tool_output
                else:
                    output_str = str(tool_output)

                yield f"data: {json.dumps({'type': 'skill_end', 'name': tool_name, 'output': output_str[:200]}, ensure_ascii=False)}\n\n"

                # 如果是音乐工具，解析输出并发送音乐控制事件
                if tool_name in ["play_song", "pause_song", "resume_song", "stop_song", "next_song"]:
                    try:
                        music_data = json.loads(output_str)
                        action = music_data.get("action")
                        if action and action != "none":
                            music_event = {"type": "music", "action": action}
                            if music_data.get("song"):
                                music_event["song"] = music_data["song"]
                            yield f"data: {json.dumps(music_event, ensure_ascii=False)}\n\n"
                            print(f"[Chat] 发送音乐事件: {music_event}")
                    except (json.JSONDecodeError, TypeError) as e:
                        print(f"[Chat] 解析音乐事件失败: {e}, output={output_str[:100]}")

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

    # 儿歌相关意图
    if isinstance(intent, PlaySongIntent):
        print(f"[Chat] 播放儿歌: {intent.song_name or '随机'}")
        return StreamingResponse(
            stream_play_song_direct(song_name=intent.song_name),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    if isinstance(intent, PauseSongIntent):
        print("[Chat] 暂停儿歌")
        return StreamingResponse(
            stream_pause_song_direct(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    if isinstance(intent, ResumeSongIntent):
        print("[Chat] 继续播放儿歌")
        return StreamingResponse(
            stream_resume_song_direct(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    if isinstance(intent, StopSongIntent):
        print("[Chat] 停止播放儿歌")
        return StreamingResponse(
            stream_stop_song_direct(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    if isinstance(intent, NextSongIntent):
        print("[Chat] 下一首儿歌")
        return StreamingResponse(
            stream_next_song_direct(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    if isinstance(intent, ListSongsIntent):
        print("[Chat] 返回儿歌列表")
        return StreamingResponse(
            stream_list_songs_direct(),
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
