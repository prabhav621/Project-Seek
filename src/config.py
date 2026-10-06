import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum

class ModelTier(str, Enum):
    # STATIC ANCHORS FOR V1/V2 LEGACY ROUTES
    PRO_PRIMARY = "nvidia_nim/nvidia/nemotron-3-ultra-550b-a55b"
    PRO_SAFETY_NET = "cloudflare/@cf/meta/llama-3-8b-instruct"
    FLASH = "gemini/gemini-3.5-flash"
    FLASH_LITE = "gemini/gemini-3.5-flash-lite"

class Capability(str, Enum):
    # NEW V3 DYNAMIC ROUTING CAPABILITIES
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
    # NEW V3 TASKS
    STRATEGY_SYNTHESIS = 'strategy_synthesis'
    LIBRARIAN_MERGE = 'librarian_merge'
    REVERSE_RAG = 'reverse_rag'

# V3 DYNAMIC FALLBACK MATRIX (Only used for new tasks)
MODEL_POOLS = {
    Capability.CODE_EXPERT: [
        "openrouter/deepseek/deepseek-coder", 
        "openrouter/qwen/qwen-2.5-coder-32b-instruct",
        "cloudflare/@cf/meta/llama-3-8b-instruct"
    ],
    Capability.DEEP_REASONING: [
        "openrouter/deepseek/deepseek-r1",
        "openrouter/anthropic/claude-3.5-sonnet",
        "openrouter/openai/o1-mini",
        "openrouter/google/gemini-2.5-pro",
        "openrouter/meta-llama/llama-3.1-70b-instruct",
        "nvidia_nim/meta/llama-3.1-70b-instruct",
        "cloudflare/@cf/meta/llama-3-8b-instruct"
    ],
    Capability.BUSINESS_LOGIC: [
        "openrouter/meta-llama/llama-3.1-70b-instruct",
        "nvidia_nim/meta/llama-3.1-70b-instruct",
        "cloudflare/@cf/meta/llama-3-8b-instruct"
    ],
    Capability.FAST_CREATIVE: [
        "gemini/gemini-3.5-flash",
        "openrouter/google/gemini-2.5-flash",
        "openrouter/meta-llama/llama-3.1-8b-instruct",
        "cloudflare/@cf/meta/llama-3.1-8b-instruct"
    ]
}

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

    # LEGACY V1/V2 ROUTER (DO NOT MODIFY)
    def get_model_for_task(self, task: TaskType) -> str:
        if task in [TaskType.DEEP_KATA, TaskType.SEEK_CHAT, TaskType.APHORISM, TaskType.INVERSION_PROMPT]:
            return ModelTier.PRO_PRIMARY.value
        elif task == TaskType.QUICK_KATA:
            return ModelTier.FLASH.value
        else:
            return ModelTier.FLASH_LITE.value

    # NEW V3 DYNAMIC ROUTER
    def get_pool_for_capability(self, capability: Capability) -> list:
        return MODEL_POOLS.get(capability, MODEL_POOLS[Capability.FAST_CREATIVE])

settings = Settings()

