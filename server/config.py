"""配置管理"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 6002
    DEBUG: bool = True

    # CORS
    ALLOWED_ORIGINS: str = "*"

    # LLM 配置
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    OPENAI_MODEL: str = "qwen-plus"

    # ASR 配置
    ASR_BASE_URL: str = "http://127.0.0.1:10095"

    # TTS 配置 (SiliconFlow IndexTTS-2 云端)
    TTS_BASE_URL: str = "https://api.siliconflow.cn/v1/audio/speech"
    TTS_MODEL: str = "IndexTeam/IndexTTS-2"
    TTS_VOICE: str = "alex"
    TTS_API_KEY: str = ""  # 使用 OPENAI_API_KEY 或单独配置

    # 数据目录
    DATA_ROOT: str = os.path.join(os.path.dirname(__file__), "skills")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
