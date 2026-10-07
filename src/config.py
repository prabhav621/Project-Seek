import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum

class Tier(str, Enum):
    PRO = "pro"           # Deep Reasoning: Lenses, Librarian, Brick Interrogation, Aphorisms
    FLASH = "flash"       # User-Facing Chat, Quick Katas, /strategize
    LITE = "lite"         # Bulk Ingestion, Backfill, Tagging, Subtitles, Hooks

# Backward compatibility alias
class ModelTier(str, Enum):
    PRO_PRIMARY = "pro"
    PRO_SAFETY_NET = "pro_safety"
    FLASH = "flash"
    FLASH_LITE = "lite"

class Capability(str, Enum):
    CODE_EXPERT = 'coding_expert'
    DEEP_REASONING = 'deep_reasoning'
    BUSINESS_LOGIC = 'business_logic'
    FAST_CREATIVE = 'fast_creative'
    EMBEDDINGS = 'embeddings'

class TaskType(str, Enum):
    # LEGACY TASKS
    DEEP_KATA = 'deep_kata'
    SEEK_CHAT = 'seek_chat'
    APHORISM = 'aphorism'
    INVERSION_PROMPT = 'inversion_prompt'
    QUICK_KATA = 'quick_kata'
    REPLY_ANALYSIS = 'reply_analysis'
    TAGGING = 'tagging'
    SUGGESTION_HOOKS = 'suggestion_hooks'
    # V3 TASKS
    STRATEGY_SYNTHESIS = 'strategy_synthesis'
    LIBRARIAN_MERGE = 'librarian_merge'
    REVERSE_RAG = 'reverse_rag'
    ASK_BRICK = 'ask_brick'
    APPLY_LENS = 'apply_lens'

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///seek.db"
    gemini_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    residential_proxy_url: str = ""

    # Sovereign Matrix Keys
    nvidia_api_key: str = ""
    openrouter_api_key: str = ""
    cloudflare_api_key: str = ""
    cloudflare_account_id: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_tier_for_task(self, task: TaskType) -> Tier:
        if task in [TaskType.DEEP_KATA, TaskType.APHORISM, TaskType.INVERSION_PROMPT, 
                    TaskType.LIBRARIAN_MERGE, TaskType.REVERSE_RAG, TaskType.ASK_BRICK, TaskType.APPLY_LENS]:
            return Tier.PRO
        elif task in [TaskType.QUICK_KATA, TaskType.STRATEGY_SYNTHESIS]:
            return Tier.FLASH
        else:
            return Tier.LITE

    # Backward compatibility helper for legacy call sites
    def get_model_for_task(self, task: TaskType) -> str:
        return self.get_tier_for_task(task).value

settings = Settings()
