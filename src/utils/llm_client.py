import litellm
import logging
import os
import time
from src.config import settings, ModelTier
from src.utils.dynamic_router import get_top_free_models

logger = logging.getLogger(__name__)

# Apply environmental variables for LiteLLM providers that strictly require them
if settings.cloudflare_api_key:
    os.environ["CLOUDFLARE_API_KEY"] = settings.cloudflare_api_key
if settings.cloudflare_account_id:
    os.environ["CLOUDFLARE_ACCOUNT_ID"] = settings.cloudflare_account_id

def _apply_provider_kwargs(kwargs, target_model):
    # Clear out leftover routing parameters from previous fallback attempts
    if "api_base" in kwargs:
        del kwargs["api_base"]
    if "extra_body" in kwargs:
        del kwargs["extra_body"]

    if "gemini" in target_model:
        kwargs["api_key"] = settings.gemini_api_key

    # NVIDIA NIM
    elif "nvidia_nim" in target_model:
        kwargs["api_key"] = settings.nvidia_api_key
        # Special configuration for Nemotron to enable reasoning tokens
        if "nemotron-3-ultra" in target_model:
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}}
            
    # OPENROUTER
    elif "openrouter" in target_model:
        kwargs["api_key"] = settings.openrouter_api_key
        # Highly recommended to prevent unannounced blocking
        kwargs["extra_headers"] = {
            "HTTP-Referer": "https://github.com/prabhav621/Project-Seek",
            "X-Title": "Project Seek"
        }
        
    # CLOUDFLARE
    elif "cloudflare" in target_model:
        pass

    return kwargs

def _get_cascade_sequence(target_model):
    if target_model == ModelTier.PRO_PRIMARY.value:
        # Slot 1: Static Primary
        sequence = [
            (ModelTier.PRO_PRIMARY.value, 45, "Nvidia NIM (Nemotron 550B)")
        ]
        
        # Slots 2, 3, 4: Dynamic OpenRouter Sweepers
        dynamic_models = get_top_free_models(limit=3)
        for i, m in enumerate(dynamic_models):
            # LiteLLM format for openrouter is openrouter/model_id
            slug = f"openrouter/{m['id']}"
            name = f"OpenRouter (Dynamic #{i+1}: {m['name']} | {m['params']}B)"
            # Asymmetric Timeout: 20s for highly congested dynamic models
            sequence.append((slug, 20, name))
            
        # Slot 5: Static Safety Net
        sequence.append(
            (ModelTier.PRO_SAFETY_NET.value, 15, "Cloudflare (Llama 3 8B)")
        )
        
        # Slot 6: Doomsday Fallback
        sequence.append(
            (ModelTier.FLASH.value, 15, "Gemini Flash (Doomsday Fallback)")
        )
        return sequence
        
    return [(target_model, 30, target_model)]

def generate_completion_sync(model: str, messages: list = None, **kwargs) -> str:
    """
    Synchronous completion with 5-Slot cascade.
    Accepts either:
      - messages: list of {"role": ..., "content": ...} dicts (direct callers)
      - contents: str (retry.py adapter pattern, auto-converted to messages)
    Additional kwargs: system_instruction, temperature, json_mode
    """
    # ─── Adapter: convert 'contents' string to messages list ───
    if messages is None:
        messages = []
    contents = kwargs.pop("contents", None)
    system_instruction = kwargs.pop("system_instruction", None)
    temperature = kwargs.pop("temperature", None)
    json_mode = kwargs.pop("json_mode", False)

    if contents and not messages:
        messages = [{"role": "user", "content": str(contents)}]
    if system_instruction:
        messages = [{"role": "system", "content": system_instruction}] + messages
    if temperature is not None:
        kwargs["temperature"] = temperature

    cascade = _get_cascade_sequence(model)

    if "max_tokens" not in kwargs:
        kwargs["max_tokens"] = 2048

    for model_str, timeout_sec, name in cascade:
        kwargs = _apply_provider_kwargs(kwargs, model_str)
        try:
            # Sync throttle: prevents rate limit violations.
            # Safe because sync callers run inside asyncio.to_thread().
            time.sleep(4.0)
            print(f"\n📡 Sending request to {name} [Timeout: {timeout_sec}s]...")
            response = litellm.completion(
                model=model_str,
                messages=messages,
                drop_params=True,
                timeout=timeout_sec,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            logger.warning(f"{name} failed: {e}")
            continue

    error_msg = "FATAL ERROR: All cascade slots exhausted."
    print(f"❌ {error_msg}")
    raise RuntimeError(error_msg)

async def generate_completion_async(model: str, messages: list = None, **kwargs) -> str:
    """
    Async completion with 5-Slot cascade.
    Accepts both messages (list) and contents (str) patterns.
    """
    # ─── Adapter: convert 'contents' string to messages list ───
    if messages is None:
        messages = []
    contents = kwargs.pop("contents", None)
    system_instruction = kwargs.pop("system_instruction", None)
    temperature = kwargs.pop("temperature", None)

    if contents and not messages:
        messages = [{"role": "user", "content": str(contents)}]
    if system_instruction:
        messages = [{"role": "system", "content": system_instruction}] + messages
    if temperature is not None:
        kwargs["temperature"] = temperature

    cascade = _get_cascade_sequence(model)

    if "max_tokens" not in kwargs:
        kwargs["max_tokens"] = 2048

    for model_str, timeout_sec, name in cascade:
        kwargs = _apply_provider_kwargs(kwargs, model_str)
        try:
            logger.info(f"Async request to {name} [Timeout: {timeout_sec}s]...")
            response = await litellm.acompletion(
                model=model_str,
                messages=messages,
                drop_params=True,
                timeout=timeout_sec,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Async {name} failed: {e}")
            continue

    raise RuntimeError("Async FATAL ERROR: All cascade slots exhausted.")


def generate_chat_sync(model: str, messages: list, system_instruction: str = None, temperature: float = 0.7) -> str:
    """
    Synchronous multi-turn chat wrapper. Accepts a full message history list
    and optional system instruction, then routes through the 5-Slot cascade.
    Used by SeekChat for Socratic dialogue.
    """
    if system_instruction:
        messages = [{"role": "system", "content": system_instruction}] + messages
    return generate_completion_sync(model, messages, temperature=temperature)

