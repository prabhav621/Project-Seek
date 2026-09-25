import os
from enum import Enum
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")

class ModelTier(str, Enum):
    PRO = "openrouter/deepseek/deepseek-r1:free"
    PRO_FALLBACK_1 = "sambanova/Meta-Llama-3.1-70B-Instruct"
    PRO_FALLBACK_2 = "groq/llama3-70b-8192"
    FLASH_LITE = "gemini/gemini-3.5-flash-lite"
    FLASH = "gemini/gemini-3.5-flash-lite"
    EMBEDDING = "gemini/gemini-embedding-2"

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
    database_url: str = "postgresql://seek_user:seek_password@localhost:5432/seek_db"
    gemini_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    krutrim_api_key: str = ""
    residential_proxy_url: str = ""
    
    # LiteLLM Provider Keys
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    sambanova_api_key: str = ""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    def get_model_for_task(self, task: TaskType) -> ModelTier:
        if task in (TaskType.DEEP_KATA, TaskType.SEEK_CHAT, TaskType.APHORISM, TaskType.INVERSION_PROMPT):
            return ModelTier.PRO
        elif task in (TaskType.QUICK_KATA, ):
            return ModelTier.FLASH
        elif task in (TaskType.REPLY_ANALYSIS, TaskType.TAGGING, TaskType.SUGGESTION_HOOKS):
            return ModelTier.FLASH_LITE
        else:
            return ModelTier.FLASH

settings = Settings()
