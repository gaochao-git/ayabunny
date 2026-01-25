"""VAD WebSocket API

内置 Silero VAD 模型，不需要外部服务
WebSocket 端点: /ws/vad
"""

import json
import numpy as np
import torch
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# 设置线程数（避免多线程开销）
torch.set_num_threads(1)

# 全局模型（启动时加载一次）
_vad_model = None
_vad_utils = None

SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # Silero VAD 推荐的 chunk 大小 (32ms @ 16kHz)


def get_vad_model():
    """获取 VAD 模型（懒加载）"""
    global _vad_model, _vad_utils
    if _vad_model is None:
        print("[VAD] 加载 Silero VAD 模型...")
        _vad_model, _vad_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        print("[VAD] 模型加载完成")
    return _vad_model, _vad_utils


class SileroVADProcessor:
    """Silero VAD 流式处理器"""

    def __init__(self, model, threshold=0.5, min_speech_ms=250, min_silence_ms=300):
        self.model = model
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
        self.model.reset_states()

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
        speech_prob = self.model(audio_tensor, SAMPLE_RATE).item()
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


@router.websocket("/vad")
async def vad_websocket(websocket: WebSocket):
    """VAD WebSocket 端点"""
    await websocket.accept()
    client_id = id(websocket)
    print(f"[VAD] 客户端连接: {client_id}")

    # 获取模型
    model, _ = get_vad_model()

    # 创建处理器
    vad_processor = SileroVADProcessor(
        model=model,
        threshold=0.5,
        min_speech_ms=250,
        min_silence_ms=500,
    )

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

            # 处理二进制消息（音频数据）
            if "bytes" in message:
                audio_buffer += message["bytes"]

                # 首次收到音频时打印
                if frame_count == 0 and len(audio_buffer) > 0:
                    print(f"[VAD] 开始接收音频, 缓冲区: {len(audio_buffer)} bytes")

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
    try:
        model, _ = get_vad_model()
        if model is not None:
            return {"status": "healthy", "service": "silero-vad", "integrated": True}
    except Exception as e:
        return {"status": "unhealthy", "service": "silero-vad", "error": str(e)}
    return {"status": "unhealthy", "service": "silero-vad"}
