import litellm
import logging
import os
import time
from typing import List, Tuple, Optional
from src.config import settings, Tier, ModelTier
from src.utils.dynamic_router import get_top_free_reasoning_models, get_top_free_flash_models

logger = logging.getLogger(__name__)

# Apply environmental variables for LiteLLM providers that strictly require them
if settings.cloudflare_api_key:
    os.environ["CLOUDFLARE_API_KEY"] = settings.cloudflare_api_key
if settings.cloudflare_account_id:
    os.environ["CLOUDFLARE_ACCOUNT_ID"] = settings.cloudflare_account_id

# Global flags for litellm safety
litellm.drop_params = True
litellm.suppress_debug_info = True

def _apply_provider_kwargs(kwargs: dict, target_model: str) -> dict:
    """Configures credentials, headers, and model-specific parameters."""
    kwargs = kwargs.copy()
    if "api_base" in kwargs:
        del kwargs["api_base"]
    if "extra_body" in kwargs:
        del kwargs["extra_body"]

    # Pop json_mode so it doesn't get passed as an invalid parameter to providers like NVIDIA NIM
    json_mode = kwargs.pop("json_mode", False)
    if json_mode:
        if ("gemini" in target_model or "openrouter" in target_model) and "nvidia" not in target_model:
            kwargs["response_format"] = {"type": "json_object"}

    # Gemini 3.x recommends temperature = 1.0 to avoid loops and degraded performance
    if ("gemini-3" in target_model or "gemini-2.5" in target_model) and "temperature" in kwargs:
        if kwargs["temperature"] is not None and kwargs["temperature"] < 1.0:
            kwargs["temperature"] = 1.0

    if "gemini" in target_model:
        kwargs["api_key"] = settings.gemini_api_key

    elif "nvidia_nim" in target_model:
        kwargs["api_key"] = settings.nvidia_api_key
        if "nemotron-3-ultra" in target_model:
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}}
            
    elif "openrouter" in target_model:
        kwargs["api_key"] = settings.openrouter_api_key
        kwargs["extra_headers"] = {
            "HTTP-Referer": "https://github.com/prabhav621/Project-Seek",
            "X-Title": "Project Seek"
        }
        
    elif "cloudflare" in target_model:
        kwargs["api_key"] = settings.cloudflare_api_key

    return kwargs

def _get_cascade_sequence(target: str) -> List[Tuple[str, int, str]]:
    """
    Returns ordered (model_slug, timeout_seconds, human_label) cascade for a Tier or specific model.
    """
    # ─── 1. PRO TIER: Deep Reasoning ───
    if target in [Tier.PRO.value, ModelTier.PRO_PRIMARY.value, "pro"]:
        sequence = [
            ("nvidia_nim/nvidia/nemotron-3-ultra-550b-a55b", 45, "NVIDIA NIM (Nemotron 550B)")
        ]
        
        # Dynamic OpenRouter Free Reasoning Sweepers (>= 70B)
        free_reasoners = get_top_free_reasoning_models(limit=2)
        for i, m in enumerate(free_reasoners):
            slug = f"openrouter/{m['id']}" if not m['id'].startswith("openrouter/") else m['id']
            sequence.append((slug, 25, f"OpenRouter (Free Heavy #{i+1}: {m['name']})"))
            
        # Paid Frontier Reasoning Fallbacks (Protected by $1 Key Spending Limit)
        sequence.append(("openrouter/deepseek/deepseek-r1", 45, "OpenRouter (DeepSeek R1 Paid)"))
        sequence.append(("openrouter/anthropic/claude-sonnet-4.5", 30, "OpenRouter (Claude Sonnet 4.5 Paid)"))
        sequence.append(("openrouter/meta-llama/llama-3.1-70b-instruct", 25, "OpenRouter (Llama 3.1 70B Paid)"))
        
        # Cloudflare Edge Safety Net (70B Heavyweight + 8B Fallback)
        sequence.append(("cloudflare/@cf/meta/llama-3.3-70b-instruct-fp8-fast", 25, "Cloudflare (Llama 3.3 70B FP8)"))
        sequence.append(("cloudflare/@cf/meta/llama-3.1-8b-instruct", 15, "Cloudflare (Llama 3.1 8B Safety Net)"))
        return sequence

    # ─── 2. FLASH TIER: User-Facing Chat, Brick Interrogation, Quick Katas ───
    elif target in [Tier.FLASH.value, ModelTier.FLASH.value, "flash"]:
        sequence = [
            ("gemini/gemini-3.5-flash-lite", 60, "Gemini 3.5 Flash Lite (500 RPD)"),
            ("gemini/gemini-3.1-flash-lite", 60, "Gemini 3.1 Flash Lite (500 RPD)")
        ]
        
        # Dynamic OpenRouter Free Flash Sweepers (< 70B)
        free_flash = get_top_free_flash_models(limit=2)
        for i, m in enumerate(free_flash):
            slug = f"openrouter/{m['id']}" if not m['id'].startswith("openrouter/") else m['id']
            sequence.append((slug, 45, f"OpenRouter (Free Flash #{i+1}: {m['name']})"))
            
        # Ultra-Cheap Paid Flash Fallbacks (Protected by $1 Key Spending Limit)
        sequence.append(("openrouter/meta-llama/llama-3.1-8b-instruct", 30, "OpenRouter (Llama 3.1 8B Paid)"))
            
        sequence.append(("cloudflare/@cf/meta/llama-3.1-8b-instruct", 30, "Cloudflare (Llama 3.1 8B)"))
        return sequence

    # ─── 3. LITE TIER: Bulk Ingestion, Backfill, Tagging, Subtitles, Hooks ───
    elif target in [Tier.LITE.value, ModelTier.FLASH_LITE.value, "lite"]:
        sequence = [
            ("gemini/gemini-3.5-flash-lite", 60, "Gemini 3.5 Flash Lite (Bulk Slot 1)"),
            ("gemini/gemini-3.1-flash-lite", 60, "Gemini 3.1 Flash Lite (Bulk Slot 2)")
        ]
        
        free_flash = get_top_free_flash_models(limit=2)
        for i, m in enumerate(free_flash):
            slug = f"openrouter/{m['id']}" if not m['id'].startswith("openrouter/") else m['id']
            sequence.append((slug, 45, f"OpenRouter (Free Lite #{i+1}: {m['name']})"))
            
        # Ultra-Cheap Paid Lite Fallback
        sequence.append(("openrouter/meta-llama/llama-3.1-8b-instruct", 30, "OpenRouter (Llama 3.1 8B Paid)"))
            
        sequence.append(("cloudflare/@cf/meta/llama-3.1-8b-instruct", 30, "Cloudflare (Llama 3.1 8B Plain-Text)"))
        return sequence

    # Direct explicit model passthrough
    return [(target, 30, target)]

def generate_completion_sync(model: str, messages: list = None, **kwargs) -> str:
    """
    Synchronous completion with unified cascade and 402 circuit breaker.
    """
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
        # Default safety limit: PRO gets 4096, others get 1500 to protect in-flight budget
        kwargs["max_tokens"] = 4096 if "pro" in str(model).lower() else 1500

    skip_openrouter = False

    for model_str, timeout_sec, name in cascade:
        if skip_openrouter and "openrouter" in model_str:
            continue

        call_kwargs = _apply_provider_kwargs(kwargs, model_str)
        try:
            logger.info(f"Routing sync to {name} [{model_str}]...")
            response = litellm.completion(
                model=model_str,
                messages=messages,
                drop_params=True,
                timeout=timeout_sec,
                num_retries=0,
                **call_kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            logger.warning(f"Model {name} ({model_str}) failed: {err_str}. Failing over...")
            
            # Circuit breaker: if OpenRouter is out of credits (402), skip all remaining OpenRouter models
            if "402" in err_str or "openrouter_credits" in err_str:
                logger.warning("OpenRouter 402/insufficient credits detected. Tripping circuit breaker for this request.")
                skip_openrouter = True
            continue

    raise RuntimeError(f"FATAL: All cascade slots exhausted for target tier: {model}")

async def generate_completion_async(model: str, messages: list = None, **kwargs) -> str:
    """
    Asynchronous completion with unified cascade and 402 circuit breaker.
    """
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
        kwargs["max_tokens"] = 4096 if "pro" in str(model).lower() else 1500

    skip_openrouter = False

    for model_str, timeout_sec, name in cascade:
        if skip_openrouter and "openrouter" in model_str:
            continue

        call_kwargs = _apply_provider_kwargs(kwargs, model_str)
        try:
            logger.info(f"Routing async to {name} [{model_str}]...")
            response = await litellm.acompletion(
                model=model_str,
                messages=messages,
                drop_params=True,
                timeout=timeout_sec,
                num_retries=0,
                **call_kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            logger.warning(f"Async {name} ({model_str}) failed: {err_str}. Failing over...")
            if "402" in err_str or "openrouter_credits" in err_str:
                logger.warning("OpenRouter 402/insufficient credits detected. Tripping circuit breaker for this request.")
                skip_openrouter = True
            continue

    raise RuntimeError(f"Async FATAL: All cascade slots exhausted for target tier: {model}")
