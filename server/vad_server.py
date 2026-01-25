#!/usr/bin/env python3
"""
FunASR VAD WebSocket Server

启动方式: python vad_server.py
默认端口: 10096
"""

import asyncio
import json
import numpy as np
import websockets
from funasr import AutoModel

# 加载 VAD 模型
print("[VAD Server] 加载 FSMN-VAD 模型...")
vad_model = AutoModel(model="fsmn-vad", model_revision="v2.0.4")
print("[VAD Server] 模型加载完成")

# 配置
HOST = "0.0.0.0"
PORT = 10096
SAMPLE_RATE = 16000
CHUNK_SIZE = 3200  # 0.2秒 @16kHz (减小以提高响应速度)


async def handle_client(websocket, path=None):
    """处理客户端连接"""
    client_id = id(websocket)
    print(f"[VAD Server] 客户端连接: {client_id}")

    audio_buffer = b""
    is_speaking = False
    frame_count = 0
    vad_cache = {}  # 持久化 VAD 缓存，用于跟踪跨 chunk 的状态

    # 防抖参数
    last_speech_start_frame = 0  # 上次发送 speech_start 的帧号
    last_speech_end_frame = 0    # 上次发送 speech_end 的帧号
    COOLDOWN_FRAMES = 10         # 冷却时间（帧数），约 2 秒 @ 0.2秒/帧
    MIN_SPEECH_FRAMES = 3        # 语音开始后最少持续帧数才发送结束

    try:
        async for message in websocket:
            # 处理配置消息（JSON）
            if isinstance(message, str):
                try:
                    config = json.loads(message)
                    print(f"[VAD Server] 收到配置: {config}")
                    if config.get("is_speaking") == False:
                        print(f"[VAD Server] 客户端 {client_id} 结束")
                        break
                    continue
                except json.JSONDecodeError:
                    pass

            # 处理音频数据（二进制）
            if isinstance(message, bytes):
                audio_buffer += message

                # 首次收到音频数据时打印
                if frame_count == 0 and len(audio_buffer) > 0:
                    print(f"[VAD Server] 开始接收音频数据, 缓冲区大小: {len(audio_buffer)} bytes")

                # 累积足够数据后进行 VAD 检测
                if len(audio_buffer) >= CHUNK_SIZE * 2:  # int16 = 2 bytes
                    frame_count += 1
                    if frame_count == 1:
                        print(f"[VAD Server] 开始 VAD 检测")

                    # 转换为 numpy array
                    audio_data = np.frombuffer(audio_buffer[:CHUNK_SIZE * 2], dtype=np.int16)
                    audio_float = audio_data.astype(np.float32) / 32768.0

                    # 计算音量
                    volume = np.abs(audio_float).mean() * 100

                    # 运行 VAD
                    try:
                        result = vad_model.generate(
                            input=audio_float,
                            cache=vad_cache,  # 使用持久化缓存
                            is_final=False,
                            chunk_size=200,
                        )

                        # 解析 VAD 结果
                        # FunASR VAD 返回格式: [[start, end], ...]
                        # - [[start, -1]] 表示语音开始，正在进行中
                        # - [[-1, end]] 表示语音结束
                        # - [[start, end]] 表示完整语音段
                        if result and len(result) > 0:
                            vad_segments = result[0].get("value", [])

                            # 判断是否检测到语音
                            # 如果有 segment 且最后一个 segment 的 end 是 -1，表示语音正在进行
                            is_speech_ongoing = False
                            is_speech_ended = False

                            if vad_segments:
                                last_seg = vad_segments[-1]
                                if len(last_seg) == 2:
                                    start, end = last_seg
                                    if end == -1:  # 语音正在进行
                                        is_speech_ongoing = True
                                    elif start == -1:  # 语音刚结束
                                        is_speech_ended = True
                                    else:  # 完整语音段
                                        is_speech_ended = True

                            # 每帧都打印详细 VAD 结果
                            if vad_segments or frame_count <= 5:
                                print(f"[VAD DEBUG] 帧{frame_count}: vad_segments={vad_segments}, ongoing={is_speech_ongoing}, ended={is_speech_ended}")

                            # 检测到语音开始（基于 VAD 事件 + 冷却时间）
                            if is_speech_ongoing and not is_speaking:
                                # 检查冷却时间
                                if frame_count - last_speech_end_frame >= COOLDOWN_FRAMES:
                                    is_speaking = True
                                    last_speech_start_frame = frame_count
                                    await websocket.send(json.dumps({
                                        "text": "speech_start",
                                        "is_speaking": True
                                    }))
                                    print(f"[VAD Server] >>> 检测到语音开始! 音量={volume:.2f}")
                                else:
                                    print(f"[VAD DEBUG] 语音开始被冷却跳过 (冷却剩余: {COOLDOWN_FRAMES - (frame_count - last_speech_end_frame)} 帧)")

                            # 语音结束（基于 VAD 事件 + 最小持续时间）
                            elif is_speech_ended and is_speaking:
                                # 检查最小语音持续时间
                                if frame_count - last_speech_start_frame >= MIN_SPEECH_FRAMES:
                                    is_speaking = False
                                    last_speech_end_frame = frame_count
                                    await websocket.send(json.dumps({
                                        "text": "",
                                        "is_speaking": False,
                                        "is_final": True
                                    }))
                                    print(f"[VAD Server] >>> 检测到语音结束! 音量={volume:.2f}")
                                else:
                                    print(f"[VAD DEBUG] 语音结束被跳过 (持续不足: {frame_count - last_speech_start_frame} < {MIN_SPEECH_FRAMES} 帧)")

                            # 每10帧打印一次状态
                            if frame_count % 10 == 0:
                                print(f"[VAD] 帧{frame_count}: 音量={volume:.2f}, 状态={'说话中' if is_speaking else '静音'}")

                    except Exception as e:
                        print(f"[VAD Server] VAD 处理错误: {e}")

                    # 保留部分数据用于重叠
                    audio_buffer = audio_buffer[CHUNK_SIZE:]

    except websockets.exceptions.ConnectionClosed:
        print(f"[VAD Server] 客户端断开: {client_id}")
    except Exception as e:
        print(f"[VAD Server] 错误: {e}")
    finally:
        print(f"[VAD Server] 客户端 {client_id} 已断开")


async def main():
    """启动服务器"""
    print(f"[VAD Server] 启动 WebSocket 服务: ws://{HOST}:{PORT}")

    async with websockets.serve(handle_client, HOST, PORT):
        print(f"[VAD Server] 服务已启动，等待连接...")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
