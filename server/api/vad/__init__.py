"""VAD WebSocket API

支持多种 VAD 后端，通过配置切换：
- ten: TEN VAD（轻量、低延迟）✓ 已实现
- webrtc: WebRTC VAD（超轻量、经典）✓ 已实现
- silero_torch: Silero VAD PyTorch 版（准确、重）✓ 已实现
- silero_onnx: Silero VAD ONNX 版（准确、中等）✓ 已实现
- funasr: FunASR FSMN-VAD（中文优化）⏳ 待实现

WebSocket 端点: /ws/vad
"""

import json
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from config import get_settings

router = APIRouter()

settings = get_settings()

# 默认 VAD 后端
DEFAULT_VAD_BACKEND = "ten"
SAMPLE_RATE = 16000


def get_vad_backend():
    """获取配置的 VAD 后端"""
    return getattr(settings, 'VAD_BACKEND', DEFAULT_VAD_BACKEND)


def create_vad_processor(backend: str = None, **kwargs):
    """
    创建 VAD 处理器

    Args:
        backend: VAD 后端名称
        **kwargs: 传递给处理器的参数（threshold, min_speech_ms, min_silence_ms）

    Returns:
        VAD 处理器实例
    """
    backend = backend or get_vad_backend()

    if backend == "ten":
        from .ten_vad import create_processor
        return create_processor(**kwargs)

    elif backend == "webrtc":
        from .webrtc_vad import create_processor
        return create_processor(**kwargs)

    elif backend == "silero_torch":
        from .silero_torch import create_processor
        return create_processor(**kwargs)

    elif backend == "silero_onnx":
        from .silero_onnx import create_processor
        return create_processor(**kwargs)

    elif backend == "funasr":
        # TODO: 待实现
        raise NotImplementedError("FunASR VAD 尚未实现，请使用 ten 或 webrtc")

    else:
        raise ValueError(f"未知的 VAD 后端: {backend}，支持: ten, webrtc, silero_torch, silero_onnx, funasr")


def health_check_backend(backend: str = None) -> dict:
    """健康检查指定后端"""
    backend = backend or get_vad_backend()

    if backend == "ten":
        from .ten_vad import health_check
        return health_check()

    elif backend == "webrtc":
        from .webrtc_vad import health_check
        return health_check()

    elif backend == "silero_torch":
        from .silero_torch import health_check
        return health_check()

    elif backend == "silero_onnx":
        from .silero_onnx import health_check
        return health_check()

    else:
        return {"status": "unknown", "backend": backend, "message": "待实现"}


# WebSocket chunk 大小
CHUNK_SIZES = {
    "ten": 256,          # TEN VAD 推荐 256 samples (16ms @ 16kHz)
    "webrtc": 480,       # WebRTC VAD 使用 30ms 帧 (480 samples @ 16kHz)
    "silero_torch": 512, # Silero VAD 推荐 512 samples (32ms @ 16kHz)
    "silero_onnx": 512,  # Silero VAD 推荐 512 samples (32ms @ 16kHz)
}


def get_chunk_size(backend: str = None) -> int:
    """获取 VAD 后端推荐的 chunk 大小"""
    backend = backend or get_vad_backend()
    return CHUNK_SIZES.get(backend, 512)


@router.websocket("/vad")
async def vad_websocket(websocket: WebSocket):
    """VAD WebSocket 端点"""
    await websocket.accept()
    client_id = id(websocket)

    # 获取配置的后端
    backend = get_vad_backend()
    chunk_size = get_chunk_size(backend)

    print(f"[VAD] 客户端连接: {client_id}, 后端: {backend}")

    # 创建处理器
    try:
        vad_processor = create_vad_processor(
            backend=backend,
            threshold=0.5,
            min_speech_ms=250,
            min_silence_ms=500,
        )
    except Exception as e:
        print(f"[VAD] 创建处理器失败: {e}")
        await websocket.close(code=1011, reason=str(e))
        return

    audio_buffer = b""
    frame_count = 0

    try:
        while True:
            message = await websocket.receive()

            # 处理文本消息（配置）
            if "text" in message:
                try:
                    config = json.loads(message["text"])
                    print(f"[VAD] 收到配置: {config}")

                    # 客户端结束信号
                    if config.get("is_speaking") == False:
                        print(f"[VAD] 客户端 {client_id} 结束")
                        break

                    # 动态切换 VAD 后端
                    new_backend = config.get('backend')
                    if new_backend and new_backend != backend:
                        try:
                            vad_processor = create_vad_processor(
                                backend=new_backend,
                                threshold=config.get('threshold', 0.5),
                                min_speech_ms=config.get('min_speech_ms', 250),
                                min_silence_ms=config.get('min_silence_ms', 500),
                            )
                            backend = new_backend
                            chunk_size = get_chunk_size(backend)
                            print(f"[VAD] 切换后端: {backend}, chunk_size: {chunk_size}")
                        except Exception as e:
                            print(f"[VAD] 切换后端失败: {e}")
                    else:
                        # 更新 VAD 参数
                        vad_processor.update_params(
                            threshold=config.get('threshold'),
                            min_speech_ms=config.get('min_speech_ms'),
                            min_silence_ms=config.get('min_silence_ms'),
                        )

                    if config.get('reset'):
                        vad_processor.reset()

                    continue
                except json.JSONDecodeError:
                    pass

            # 处理二进制消息（音频数据）
            if "bytes" in message:
                audio_buffer += message["bytes"]

                # 首次收到音频时打印
                if frame_count == 0 and len(audio_buffer) > 0:
                    print(f"[VAD] 开始接收音频, 缓冲区: {len(audio_buffer)} bytes, chunk_size: {chunk_size}")

                # 累积足够数据后进行 VAD 检测
                bytes_needed = chunk_size * 2  # int16 = 2 bytes

                while len(audio_buffer) >= bytes_needed:
                    frame_count += 1

                    # 提取 chunk
                    chunk_bytes = audio_buffer[:bytes_needed]
                    audio_buffer = audio_buffer[bytes_needed:]

                    # 转换为 float32（统一格式）
                    audio_int16 = np.frombuffer(chunk_bytes, dtype=np.int16)
                    audio_float = audio_int16.astype(np.float32) / 32768.0

                    # 运行 VAD
                    result = vad_processor.process(audio_float)

                    # 有事件时发送
                    if result['event']:
                        if result['event'] == 'speech_start':
                            await websocket.send_json({
                                'event': 'speech_start',
                                'text': 'speech_start',
                                'is_speaking': True,
                                'speech_prob': result['speech_prob']
                            })
                            print(f"[VAD] >>> 语音开始! prob={result['speech_prob']:.3f}")

                        elif result['event'] == 'speech_end':
                            await websocket.send_json({
                                'event': 'speech_end',
                                'text': '',
                                'is_speaking': False,
                                'is_final': True,
                                'speech_prob': result['speech_prob']
                            })
                            print(f"[VAD] >>> 语音结束! prob={result['speech_prob']:.3f}")

                    # 每 50 帧打印一次状态
                    if frame_count % 50 == 0:
                        status = '说话中' if result['is_speaking'] else '静音'
                        print(f"[VAD] 帧{frame_count}: prob={result['speech_prob']:.3f}, {status}")

    except WebSocketDisconnect as e:
        print(f"[VAD] 客户端断开: {client_id}, code={e.code}")
    except Exception as e:
        print(f"[VAD] 错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        vad_processor.reset()
        print(f"[VAD] 客户端 {client_id} 已清理, 处理了 {frame_count} 帧")


@router.get("/vad/health")
async def vad_health():
    """检查 VAD 服务状态"""
    backend = get_vad_backend()
    result = health_check_backend(backend)
    result["configured_backend"] = backend
    return result


@router.get("/vad/backends")
async def list_backends():
    """列出可用的 VAD 后端"""
    return {
        "current": get_vad_backend(),
        "available": [
            {"id": "ten", "name": "TEN VAD", "status": "implemented", "size": "~1.3MB"},
            {"id": "webrtc", "name": "WebRTC VAD", "status": "implemented", "size": "~50KB"},
            {"id": "silero_torch", "name": "Silero VAD (PyTorch)", "status": "implemented", "size": "~2GB"},
            {"id": "silero_onnx", "name": "Silero VAD (ONNX)", "status": "implemented", "size": "~50MB"},
            {"id": "funasr", "name": "FunASR FSMN-VAD", "status": "not_implemented", "size": "~50MB"},
        ]
    }
