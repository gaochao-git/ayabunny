"""视频分析 API"""

import base64
import tempfile
import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import json

from config import get_settings

router = APIRouter()
settings = get_settings()


class FrameAnalyzeRequest(BaseModel):
    """单帧分析请求"""
    frame: str  # base64 图片
    question: str = ""  # 用户问题（可选）
    context: str = ""  # 对话上下文（可选）


class FramesAnalyzeRequest(BaseModel):
    """多帧分析请求"""
    frames: list[str]  # 多帧 base64
    question: str = ""


def extract_frames_from_video(video_path: str, interval: float = 2.0, max_frames: int = 30) -> list[str]:
    """从视频提取关键帧

    Args:
        video_path: 视频文件路径
        interval: 帧间隔（秒）
        max_frames: 最大帧数

    Returns:
        base64 编码的帧列表
    """
    try:
        import cv2
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="opencv-python 未安装，请运行: pip install opencv-python"
        )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="无法打开视频文件")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30  # 默认 30fps

    frame_interval = int(fps * interval)
    if frame_interval < 1:
        frame_interval = 1

    frames = []
    count = 0

    while cap.isOpened() and len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if count % frame_interval == 0:
            # 压缩并转 base64
            # 缩小分辨率以减少 token 消耗
            height, width = frame.shape[:2]
            max_dim = 800
            if max(height, width) > max_dim:
                scale = max_dim / max(height, width)
                frame = cv2.resize(frame, (int(width * scale), int(height * scale)))

            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frames.append(base64.b64encode(buffer).decode())

        count += 1

    cap.release()
    return frames


async def analyze_with_vision_model(
    frames: list[str],
    question: str = "",
    context: str = "",
    stream: bool = False
):
    """使用视觉模型分析图片帧

    Args:
        frames: base64 编码的图片列表
        question: 用户问题
        context: 对话上下文
        stream: 是否流式返回
    """
    # 使用视觉模型
    model = getattr(settings, 'VISION_MODEL', settings.OPENAI_MODEL)
    api_key = settings.OPENAI_API_KEY
    base_url = settings.OPENAI_BASE_URL

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        streaming=stream,
        temperature=0.7,
    )

    # 构建消息内容
    content = []

    # 添加图片
    for i, frame in enumerate(frames):
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{frame}",
                "detail": "low"  # 使用低分辨率以减少 token
            }
        })

    # 构建提示词
    if len(frames) == 1:
        prompt = question if question else "请描述这张图片的内容。"
    else:
        prompt = question if question else f"这是一段视频的 {len(frames)} 个关键帧，请描述视频的主要内容。"

    if context:
        prompt = f"对话背景：{context}\n\n{prompt}"

    content.append({"type": "text", "text": prompt})

    message = HumanMessage(content=content)

    if stream:
        return llm.astream([message])
    else:
        response = await llm.ainvoke([message])
        return response.content


@router.post("/analyze-frame")
async def analyze_frame(request: FrameAnalyzeRequest):
    """分析单帧图片（实时模式）

    返回 SSE 流式响应
    """
    async def event_generator():
        try:
            stream = await analyze_with_vision_model(
                frames=[request.frame],
                question=request.question,
                context=request.context,
                stream=True
            )

            async for chunk in stream:
                if chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/analyze-frames")
async def analyze_frames(request: FramesAnalyzeRequest):
    """分析多帧图片（短视频录制后的帧序列）

    返回 SSE 流式响应
    """
    if len(request.frames) > 30:
        raise HTTPException(status_code=400, detail="帧数不能超过 30")

    async def event_generator():
        try:
            stream = await analyze_with_vision_model(
                frames=request.frames,
                question=request.question,
                stream=True
            )

            async for chunk in stream:
                if chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/analyze-video")
async def analyze_video(
    file: UploadFile = File(...),
    question: str = Form(""),
    interval: float = Form(2.0),
):
    """分析上传的视频文件

    Args:
        file: 视频文件
        question: 用户问题
        interval: 帧提取间隔（秒）

    返回 SSE 流式响应
    """
    # 检查文件类型
    content_type = file.content_type or ""
    if not content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="请上传视频文件")

    # 保存临时文件
    suffix = ".mp4"
    if "webm" in content_type:
        suffix = ".webm"
    elif "quicktime" in content_type:
        suffix = ".mov"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 提取关键帧
        frames = extract_frames_from_video(tmp_path, interval=interval)

        if not frames:
            raise HTTPException(status_code=400, detail="无法从视频提取帧")

        async def event_generator():
            try:
                # 告知提取了多少帧
                yield f"data: {json.dumps({'type': 'info', 'content': f'已提取 {len(frames)} 个关键帧，正在分析...'})}\n\n"

                stream = await analyze_with_vision_model(
                    frames=frames,
                    question=question,
                    stream=True
                )

                async for chunk in stream:
                    if chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            finally:
                # 清理临时文件
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except HTTPException:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    except Exception as e:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))
