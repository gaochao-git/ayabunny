"""Silero VAD (ONNX) 实现

使用 ONNX Runtime 运行 Silero VAD 模型
比 PyTorch 版本轻量（~50MB vs ~2GB）

模型下载：
curl -L -o models/silero_vad.onnx "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
"""

import os
import numpy as np
from .base import BaseVADProcessor

# 全局 ONNX 会话（懒加载）
_onnx_session = None

# 模型路径
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "silero_vad.onnx")


def get_onnx_session():
    """获取 ONNX 会话"""
    global _onnx_session
    if _onnx_session is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Silero VAD ONNX 模型未找到: {MODEL_PATH}\n"
                f"请下载模型: curl -L -o {MODEL_PATH} "
                f"\"https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx\""
            )
        print(f"[VAD] 加载 Silero VAD (ONNX) 模型: {MODEL_PATH}")
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        _onnx_session = ort.InferenceSession(MODEL_PATH, sess_options=opts)
        print("[VAD] Silero VAD (ONNX) 加载完成")
    return _onnx_session


class SileroONNXVADProcessor(BaseVADProcessor):
    """Silero VAD (ONNX) 处理器"""

    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300):
        super().__init__(threshold, min_speech_ms, min_silence_ms)
        self.session = get_onnx_session()
        # ONNX 模型的隐藏状态: (2, batch, 128)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def reset(self):
        """重置状态"""
        super().reset()
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def _get_speech_prob(self, audio_chunk: np.ndarray) -> float:
        """获取语音概率"""
        # 转换为 float32
        if audio_chunk.dtype == np.int16:
            audio_float = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio_float = audio_chunk.astype(np.float32)

        # 准备输入 (1, samples)
        if audio_float.ndim == 1:
            audio_float = audio_float[np.newaxis, :]

        # 运行 ONNX 推理
        ort_inputs = {
            'input': audio_float,
            'state': self._state,
            'sr': np.array(self.sample_rate, dtype=np.int64),
        }
        out, self._state = self.session.run(None, ort_inputs)
        return float(out[0][0])


def create_processor(threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300) -> SileroONNXVADProcessor:
    """创建 Silero VAD (ONNX) 处理器"""
    return SileroONNXVADProcessor(threshold, min_speech_ms, min_silence_ms)


def health_check() -> dict:
    """健康检查"""
    try:
        session = get_onnx_session()
        if session is not None:
            return {"status": "healthy", "backend": "silero-onnx"}
    except FileNotFoundError as e:
        return {"status": "unhealthy", "backend": "silero-onnx", "error": "模型文件未找到", "hint": str(e)}
    except Exception as e:
        return {"status": "unhealthy", "backend": "silero-onnx", "error": str(e)}
    return {"status": "unhealthy", "backend": "silero-onnx"}
