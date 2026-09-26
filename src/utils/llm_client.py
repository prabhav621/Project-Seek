import litellm
import logging
import os
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
            (ModelTier.PRO_SAFETY_NET.value, 15, "Cloudflare (Llama 3.3 70B)")
        )
        return sequence
        
    return [(target_model, 30, target_model)]

def generate_completion_sync(model: str, messages: list, **kwargs) -> str:
    cascade = _get_cascade_sequence(model)

    if "max_tokens" not in kwargs:
        kwargs["max_tokens"] = 2048

    for model_str, timeout_sec, name in cascade:
        kwargs = _apply_provider_kwargs(kwargs, model_str)
        try:
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

    error_msg = "FATAL ERROR: All 5 cascade slots exhausted."
    print(f"❌ {error_msg}")
    raise RuntimeError(error_msg)

async def generate_completion_async(model: str, messages: list, **kwargs) -> str:
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

    raise RuntimeError("Async FATAL ERROR: All 5 cascade slots exhausted.")
