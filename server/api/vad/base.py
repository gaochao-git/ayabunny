"""VAD 基类"""

from abc import ABC, abstractmethod
import numpy as np


class BaseVADProcessor(ABC):
    """VAD 处理器基类"""

    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 300):
        self.threshold = threshold
        self.sample_rate = 16000
        self.min_speech_samples = int(min_speech_ms * self.sample_rate / 1000)
        self.min_silence_samples = int(min_silence_ms * self.sample_rate / 1000)
        self.is_speaking = False
        self.speech_samples = 0
        self.silence_samples = 0

    @abstractmethod
    def reset(self):
        """重置状态"""
        self.is_speaking = False
        self.speech_samples = 0
        self.silence_samples = 0

    @abstractmethod
    def _get_speech_prob(self, audio_chunk: np.ndarray) -> float:
        """获取语音概率（子类实现）"""
        pass

    def process(self, audio_chunk: np.ndarray) -> dict:
        """
        处理音频 chunk，返回 VAD 结果

        Args:
            audio_chunk: int16 或 float32 音频数据

        Returns:
            dict with keys:
                - speech_prob: 语音概率 (0-1)
                - is_speech: 是否为语音
                - event: 'speech_start' | 'speech_end' | None
        """
        speech_prob = self._get_speech_prob(audio_chunk)
        is_speech = speech_prob >= self.threshold

        event = None

        if is_speech:
            self.speech_samples += len(audio_chunk)
            self.silence_samples = 0

            if not self.is_speaking and self.speech_samples >= self.min_speech_samples:
                self.is_speaking = True
                event = 'speech_start'
        else:
            self.silence_samples += len(audio_chunk)

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

    def update_params(self, threshold: float = None, min_speech_ms: int = None, min_silence_ms: int = None):
        """更新参数"""
        if threshold is not None:
            self.threshold = threshold
        if min_speech_ms is not None:
            self.min_speech_samples = int(min_speech_ms * self.sample_rate / 1000)
        if min_silence_ms is not None:
            self.min_silence_samples = int(min_silence_ms * self.sample_rate / 1000)
