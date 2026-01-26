"""TEN VAD 实现

轻量级、低延迟的 VAD
https://github.com/TEN-framework/ten-vad
"""

import numpy as np
from .base import BaseVADProcessor

# 全局实例（懒加载）
_ten_vad_instance = None


def get_ten_vad():
    """获取 TEN VAD 实例"""
    global _ten_vad_instance
    if _ten_vad_instance is None:
        print("[VAD] 加载 TEN VAD...")
        from ten_vad import TenVad
        _ten_vad_instance = TenVad(hop_size=256, threshold=0.5)
        print("[VAD] TEN VAD 加载完成")
    return _ten_vad_instance


class TenVADProcessor(BaseVADProcessor):
    """TEN VAD 处理器"""

    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300):
        super().__init__(threshold, min_speech_ms, min_silence_ms)
        self.vad = get_ten_vad()

    def reset(self):
        """重置状态"""
        super().reset()
        # TEN VAD 没有显式的 reset 方法

    def _get_speech_prob(self, audio_chunk: np.ndarray) -> float:
        """获取语音概率"""
        # TEN VAD 需要 int16 格式
        if audio_chunk.dtype == np.float32:
            # float32 [-1, 1] -> int16
            audio_int16 = (audio_chunk * 32767).astype(np.int16)
        elif audio_chunk.dtype == np.int16:
            audio_int16 = audio_chunk
        else:
            audio_int16 = audio_chunk.astype(np.int16)

        # 处理音频（需要 256 samples）
        prob, flag = self.vad.process(audio_int16)
        return float(prob)


def create_processor(threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300) -> TenVADProcessor:
    """创建 TEN VAD 处理器"""
    return TenVADProcessor(threshold, min_speech_ms, min_silence_ms)


def health_check() -> dict:
    """健康检查"""
    try:
        vad = get_ten_vad()
        if vad is not None:
            return {"status": "healthy", "backend": "ten-vad"}
    except Exception as e:
        return {"status": "unhealthy", "backend": "ten-vad", "error": str(e)}
    return {"status": "unhealthy", "backend": "ten-vad"}
