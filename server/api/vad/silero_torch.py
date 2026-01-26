"""Silero VAD (PyTorch) 实现

使用 torch.hub 加载 Silero VAD 模型
https://github.com/snakers4/silero-vad

注意：需要安装 torch 和 torchaudio（约 2GB）
"""

import numpy as np
from .base import BaseVADProcessor

# 全局模型（懒加载）
_vad_model = None


def get_silero_model():
    """获取 Silero VAD 模型"""
    global _vad_model
    if _vad_model is None:
        print("[VAD] 加载 Silero VAD (PyTorch) 模型...")
        import torch
        torch.set_num_threads(1)
        _vad_model, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        print("[VAD] Silero VAD (PyTorch) 加载完成")
    return _vad_model


class SileroTorchVADProcessor(BaseVADProcessor):
    """Silero VAD (PyTorch) 处理器"""

    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300):
        super().__init__(threshold, min_speech_ms, min_silence_ms)
        self.model = get_silero_model()

    def reset(self):
        """重置状态"""
        super().reset()
        self.model.reset_states()

    def _get_speech_prob(self, audio_chunk: np.ndarray) -> float:
        """获取语音概率"""
        import torch

        # 转换为 float32 tensor
        if audio_chunk.dtype == np.int16:
            audio_float = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio_float = audio_chunk.astype(np.float32)

        audio_tensor = torch.from_numpy(audio_float).float()

        # 运行 VAD
        speech_prob = self.model(audio_tensor, self.sample_rate).item()
        return float(speech_prob)


def create_processor(threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300) -> SileroTorchVADProcessor:
    """创建 Silero VAD (PyTorch) 处理器"""
    return SileroTorchVADProcessor(threshold, min_speech_ms, min_silence_ms)


def health_check() -> dict:
    """健康检查"""
    try:
        model = get_silero_model()
        if model is not None:
            return {"status": "healthy", "backend": "silero-torch"}
    except Exception as e:
        return {"status": "unhealthy", "backend": "silero-torch", "error": str(e)}
    return {"status": "unhealthy", "backend": "silero-torch"}
