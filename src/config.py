import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum

class ModelTier(str, Enum):
    # The 5-Titan Matrix for PRO reasoning
    PRO_PRIMARY = "openai/deepseek-ai/DeepSeek-R1"
    PRO_FALLBACK_1 = "openai/deepseek-ai/DeepSeek-R1" 
    PRO_FALLBACK_2 = "nvidia_nim/z.ai/glm-5-3"
    PRO_FALLBACK_3 = "cloudflare/@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    PRO_FALLBACK_4 = "mistral/mistral-large-latest"
    
    # Fast models for tagging and basic tasks
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
    
    # The 5-Titan Matrix Keys
    siliconflow_api_key: str = ""
    glhf_api_key: str = ""
    nvidia_api_key: str = ""
    cloudflare_api_key: str = ""
    cloudflare_account_id: str = ""
    mistral_api_key: str = ""
    
    # Legacy keys kept for safety, can be ignored
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    sambanova_api_key: str = ""

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
