#!/usr/bin/env python3
"""
Silero VAD WebSocket Server

使用 Silero VAD 模型进行语音活动检测
比 FunASR VAD 更轻量，纯本地运行

启动方式: python silero_vad_server.py
默认端口: 10097
"""

import asyncio
import json
import numpy as np
import websockets
import torch

# 设置线程数（避免多线程开销）
torch.set_num_threads(1)

# 加载 Silero VAD 模型
print("[Silero VAD] 加载模型...")
model, utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    force_reload=False,
    trust_repo=True
)
(get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
print("[Silero VAD] 模型加载完成")

# 配置
HOST = "0.0.0.0"
PORT = 10097
SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # Silero VAD 推荐的 chunk 大小 (32ms @ 16kHz)


class SileroVADProcessor:
    """Silero VAD 流式处理器"""

    def __init__(self, threshold=0.5, min_speech_ms=250, min_silence_ms=300):
        self.threshold = threshold
        self.min_speech_samples = int(min_speech_ms * SAMPLE_RATE / 1000)
        self.min_silence_samples = int(min_silence_ms * SAMPLE_RATE / 1000)

        self.reset()

    def reset(self):
        """重置状态"""
        self.is_speaking = False
        self.speech_samples = 0
        self.silence_samples = 0
        self.triggered = False
        model.reset_states()

    def process(self, audio_chunk: np.ndarray) -> dict:
        """
        处理音频 chunk，返回 VAD 结果

        Args:
            audio_chunk: float32 音频数据，范围 [-1, 1]

        Returns:
            dict with keys:
                - speech_prob: 语音概率 (0-1)
                - is_speech: 是否为语音
                - event: 'speech_start' | 'speech_end' | None
        """
        # 转换为 tensor
        audio_tensor = torch.from_numpy(audio_chunk).float()

        # 运行 VAD
        speech_prob = model(audio_tensor, SAMPLE_RATE).item()
        is_speech = speech_prob >= self.threshold

        event = None

        if is_speech:
            self.speech_samples += len(audio_chunk)
            self.silence_samples = 0

            # 检测语音开始
            if not self.is_speaking and self.speech_samples >= self.min_speech_samples:
                self.is_speaking = True
                self.triggered = True
                event = 'speech_start'
        else:
            self.silence_samples += len(audio_chunk)

            # 检测语音结束
            if self.is_speaking and self.silence_samples >= self.min_silence_samples:
                self.is_speaking = False
                self.speech_samples = 0
                event = 'speech_end'

        return {
            'speech_prob': speech_prob,
            'is_speech': is_speech,
            'event': event,
            'is_speaking': self.is_speaking
        }


async def handle_client(websocket, path=None):
    """处理客户端连接"""
    client_id = id(websocket)
    print(f"[Silero VAD] 客户端连接: {client_id}")

    audio_buffer = b""
    frame_count = 0
    vad_processor = SileroVADProcessor(
        threshold=0.5,
        min_speech_ms=250,   # 最小语音持续时间
        min_silence_ms=500,  # 最小静音持续时间（语音结束判定）
    )

    try:
        async for message in websocket:
            # 处理配置消息（JSON）
            if isinstance(message, str):
                try:
                    config = json.loads(message)
                    print(f"[Silero VAD] 收到配置: {config}")

                    # 客户端结束信号
                    if config.get("is_speaking") == False:
                        print(f"[Silero VAD] 客户端 {client_id} 结束")
                        break

                    # 更新 VAD 参数
                    if 'threshold' in config:
                        vad_processor.threshold = config['threshold']
                    if 'min_speech_ms' in config:
                        vad_processor.min_speech_samples = int(config['min_speech_ms'] * SAMPLE_RATE / 1000)
                    if 'min_silence_ms' in config:
                        vad_processor.min_silence_samples = int(config['min_silence_ms'] * SAMPLE_RATE / 1000)
                    if config.get('reset'):
                        vad_processor.reset()

                    continue
                except json.JSONDecodeError:
                    pass

            # 处理音频数据（二进制 PCM int16）
            if isinstance(message, bytes):
                audio_buffer += message

                # 首次收到音频时打印
                if frame_count == 0 and len(audio_buffer) > 0:
                    print(f"[Silero VAD] 开始接收音频, 缓冲区: {len(audio_buffer)} bytes")

                # 累积足够数据后进行 VAD 检测
                bytes_needed = CHUNK_SIZE * 2  # int16 = 2 bytes

                while len(audio_buffer) >= bytes_needed:
                    frame_count += 1

                    # 提取 chunk
                    chunk_bytes = audio_buffer[:bytes_needed]
                    audio_buffer = audio_buffer[bytes_needed:]

                    # 转换为 float32
                    audio_int16 = np.frombuffer(chunk_bytes, dtype=np.int16)
                    audio_float = audio_int16.astype(np.float32) / 32768.0

                    # 运行 VAD
                    result = vad_processor.process(audio_float)

                    # 有事件时发送
                    if result['event']:
                        if result['event'] == 'speech_start':
                            await websocket.send(json.dumps({
                                'event': 'speech_start',
                                'text': 'speech_start',
                                'is_speaking': True,
                                'speech_prob': result['speech_prob']
                            }))
                            print(f"[Silero VAD] >>> 语音开始! prob={result['speech_prob']:.3f}")

                        elif result['event'] == 'speech_end':
                            await websocket.send(json.dumps({
                                'event': 'speech_end',
                                'text': '',
                                'is_speaking': False,
                                'is_final': True,
                                'speech_prob': result['speech_prob']
                            }))
                            print(f"[Silero VAD] >>> 语音结束! prob={result['speech_prob']:.3f}")

                    # 每 50 帧打印一次状态
                    if frame_count % 50 == 0:
                        status = '说话中' if result['is_speaking'] else '静音'
                        print(f"[Silero VAD] 帧{frame_count}: prob={result['speech_prob']:.3f}, {status}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[Silero VAD] 客户端断开: {client_id}")
    except Exception as e:
        print(f"[Silero VAD] 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        vad_processor.reset()
        print(f"[Silero VAD] 客户端 {client_id} 已断开")


async def main():
    """启动服务器"""
    print(f"[Silero VAD] 启动 WebSocket 服务: ws://{HOST}:{PORT}")

    async with websockets.serve(handle_client, HOST, PORT):
        print(f"[Silero VAD] 服务已启动，等待连接...")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
