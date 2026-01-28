"""配置管理"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8888
    DEBUG: bool = True

    # CORS
    ALLOWED_ORIGINS: str = "*"

    # LLM 配置
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.siliconflow.cn/v1"
    OPENAI_MODEL: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"

    # 视觉模型配置（用于图片问答）
    VISION_MODEL: str = "Qwen/Qwen2.5-VL-72B-Instruct"

    # ASR 配置 (SiliconFlow SenseVoice)
    ASR_BASE_URL: str = "https://api.siliconflow.cn/v1/audio/transcriptions"
    ASR_MODEL: str = "FunAudioLLM/SenseVoiceSmall"

    # TTS 配置 (SiliconFlow IndexTTS-2 云端)
    TTS_BASE_URL: str = "https://api.siliconflow.cn/v1/audio/speech"
    TTS_MODEL: str = "IndexTeam/IndexTTS-2"
    TTS_VOICE: str = "alex"
    TTS_API_KEY: str = ""  # 使用 OPENAI_API_KEY 或单独配置

    # VAD 配置
    # 可选: ten, webrtc, silero_torch, silero_onnx, funasr
    # webrtc 兼容性最好，不需要额外系统库
    VAD_BACKEND: str = "webrtc"

    # 视频配置
    VIDEO_FRAME_INTERVAL: float = 2.0  # 帧提取间隔（秒）
    VIDEO_MAX_DURATION: int = 60  # 最大录制时长（秒）
    VIDEO_FRAME_QUALITY: int = 70  # JPEG 压缩质量
    VIDEO_MAX_FRAMES: int = 30  # 单次分析最大帧数

    # 数据目录
    DATA_ROOT: str = os.path.join(os.path.dirname(__file__), "skills")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
