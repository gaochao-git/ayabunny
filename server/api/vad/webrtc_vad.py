"""WebRTC VAD 实现

Google 开发的经典 VAD，超轻量
https://github.com/wiseman/py-webrtcvad
"""

import numpy as np
from .base import BaseVADProcessor

# 全局实例（懒加载）
_webrtc_vad_instance = None


def get_webrtc_vad(aggressiveness: int = 2):
    """获取 WebRTC VAD 实例

    Args:
        aggressiveness: 0-3，越高越激进地过滤非语音
    """
    global _webrtc_vad_instance
    if _webrtc_vad_instance is None:
        print(f"[VAD] 加载 WebRTC VAD (aggressiveness={aggressiveness})...")
        import webrtcvad
        _webrtc_vad_instance = webrtcvad.Vad(aggressiveness)
        print("[VAD] WebRTC VAD 加载完成")
    return _webrtc_vad_instance


class WebRTCVADProcessor(BaseVADProcessor):
    """WebRTC VAD 处理器"""

    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300, aggressiveness: int = 2):
        super().__init__(threshold, min_speech_ms, min_silence_ms)
        self.vad = get_webrtc_vad(aggressiveness)
        self.aggressiveness = aggressiveness
        # WebRTC VAD 返回布尔值，用滑动窗口平滑
        self._history = []
        self._history_size = 5

    def reset(self):
        """重置状态"""
        super().reset()
        self._history = []

    def _get_speech_prob(self, audio_chunk: np.ndarray) -> float:
        """获取语音概率"""
        # WebRTC VAD 需要 int16 bytes 格式
        if audio_chunk.dtype == np.float32:
            audio_int16 = (audio_chunk * 32767).astype(np.int16)
        elif audio_chunk.dtype == np.int16:
            audio_int16 = audio_chunk
        else:
            audio_int16 = audio_chunk.astype(np.int16)

        audio_bytes = audio_int16.tobytes()

        # WebRTC VAD 需要 10/20/30ms 的帧
        # 16kHz, 16bit: 10ms=320bytes, 20ms=640bytes, 30ms=960bytes
        frame_duration_ms = len(audio_int16) * 1000 // self.sample_rate

        # 如果帧长度不对，尝试分割处理
        valid_durations = [10, 20, 30]
        if frame_duration_ms not in valid_durations:
            # 使用 30ms 帧处理
            frame_size = int(self.sample_rate * 30 / 1000)  # 480 samples
            if len(audio_int16) >= frame_size:
                audio_bytes = audio_int16[:frame_size].tobytes()
            else:
                # 填充到 10ms
                frame_size = int(self.sample_rate * 10 / 1000)  # 160 samples
                if len(audio_int16) < frame_size:
                    padded = np.zeros(frame_size, dtype=np.int16)
                    padded[:len(audio_int16)] = audio_int16
                    audio_bytes = padded.tobytes()
                else:
                    audio_bytes = audio_int16[:frame_size].tobytes()

        try:
            is_speech = self.vad.is_speech(audio_bytes, self.sample_rate)
        except Exception:
            # 帧长度不对时返回上一次结果
            return self._history[-1] if self._history else 0.0

        # 更新历史并计算平滑概率
        self._history.append(1.0 if is_speech else 0.0)
        if len(self._history) > self._history_size:
            self._history.pop(0)

        # 返回平滑后的概率
        return sum(self._history) / len(self._history)


def create_processor(threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300, aggressiveness: int = 2) -> WebRTCVADProcessor:
    """创建 WebRTC VAD 处理器"""
    return WebRTCVADProcessor(threshold, min_speech_ms, min_silence_ms, aggressiveness)


def health_check() -> dict:
    """健康检查"""
    try:
        vad = get_webrtc_vad()
        if vad is not None:
            return {"status": "healthy", "backend": "webrtc-vad"}
    except Exception as e:
        return {"status": "unhealthy", "backend": "webrtc-vad", "error": str(e)}
    return {"status": "unhealthy", "backend": "webrtc-vad"}
