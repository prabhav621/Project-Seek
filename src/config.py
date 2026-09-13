import os
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict

class ModelTier(str, Enum):
    PRO = "gemini-2.5-pro"
    FLASH = "gemini-2.5-flash"
    FLASH_LITE = "gemini-2.5-flash-lite"

class TaskType(str, Enum):
    DEEP_KATA = "deep_kata"
    SEEK_CHAT = "seek_chat"
    QUICK_KATA = "quick_kata"
    APHORISM = "aphorism"
    INVERSION_PROMPT = "inversion_prompt"
    REPLY_ANALYSIS = "reply_analysis"
    TAGGING = "tagging"
    SUGGESTION_HOOKS = "suggestion_hooks"

class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_key: str = ""
    gemini_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    krutrim_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def get_model_for_task(self, task: TaskType) -> ModelTier:
        """
        Tiered Model Router logic based on task type.
        """
        if task in (TaskType.DEEP_KATA, TaskType.SEEK_CHAT):
            return ModelTier.PRO
        elif task in (TaskType.QUICK_KATA, TaskType.APHORISM, TaskType.INVERSION_PROMPT):
            return ModelTier.FLASH
        elif task in (TaskType.REPLY_ANALYSIS, TaskType.TAGGING, TaskType.SUGGESTION_HOOKS):
            return ModelTier.FLASH_LITE
        else:
            return ModelTier.FLASH

settings = Settings()
