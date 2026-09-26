import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum

class ModelTier(str, Enum):
    # STATIC ANCHORS FOR THE 5-SLOT MATRIX
    PRO_PRIMARY = "nvidia_nim/nvidia/nemotron-3-ultra-550b-a55b"             # Slot 1: Nvidia 550B
    PRO_SAFETY_NET = "cloudflare/@cf/meta/llama-3.3-70b-instruct-fp8-fast"    # Slot 5: Cloudflare 70B
    
    # Fast models for tagging and basic tasks (Gemini free tier)
    FLASH = "gemini/gemini-3.5-flash-lite"
    FLASH_LITE = "gemini/gemini-3.5-flash-lite"

class TaskType(str, Enum):
    DEEP_KATA = 'deep_kata'
    SEEK_CHAT = 'seek_chat'
    APHORISM = 'aphorism'
    INVERSION_PROMPT = 'inversion_prompt'
    QUICK_KATA = 'quick_kata'
    REPLY_ANALYSIS = 'reply_analysis'
    TAGGING = 'tagging'
    SUGGESTION_HOOKS = 'suggestion_hooks'

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///seek.db"
    gemini_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    residential_proxy_url: str = ""

    # The Sovereign Matrix Keys
    nvidia_api_key: str = ""
    openrouter_api_key: str = ""
    cloudflare_api_key: str = ""
    cloudflare_account_id: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_model_for_task(self, task: TaskType) -> str:
        if task in [TaskType.DEEP_KATA, TaskType.SEEK_CHAT, TaskType.APHORISM, TaskType.INVERSION_PROMPT]:
            return ModelTier.PRO_PRIMARY.value
        elif task == TaskType.QUICK_KATA:
            return ModelTier.FLASH.value
        else:
            return ModelTier.FLASH_LITE.value

settings = Settings()
