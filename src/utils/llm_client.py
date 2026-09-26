import litellm
import logging
import os
from src.config import settings, ModelTier

logger = logging.getLogger(__name__)

# Apply environmental variables for LiteLLM providers that strictly require them
if settings.cloudflare_api_key:
    os.environ["CLOUDFLARE_API_KEY"] = settings.cloudflare_api_key
if settings.cloudflare_account_id:
    os.environ["CLOUDFLARE_ACCOUNT_ID"] = settings.cloudflare_account_id

def _apply_provider_kwargs(kwargs, target_model, tier_level="PRIMARY"):
    # Clear out leftover routing parameters from previous fallback attempts
    if "api_base" in kwargs:
        del kwargs["api_base"]
    if "extra_body" in kwargs:
        del kwargs["extra_body"]

    if "gemini" in target_model:
        kwargs["api_key"] = settings.gemini_api_key

    # The 4-Titan Sovereign Matrix Routing Logic
    elif "nvidia_nim" in target_model:
        kwargs["api_key"] = settings.nvidia_api_key
        # Special configuration for Nemotron to enable reasoning tokens
        if "nemotron-3-ultra" in target_model:
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}}
            
    elif "cloudflare" in target_model:
        # API keys are loaded via os.environ for Cloudflare in LiteLLM
        pass

    return kwargs

def _get_cascade_sequence(target_model):
    if target_model == ModelTier.PRO_PRIMARY.value:
        return [
            (ModelTier.PRO_PRIMARY.value, "PRIMARY", "Nvidia NIM (Nemotron 550B)"),
            (ModelTier.PRO_FALLBACK_1.value, "FALLBACK_1", "Nvidia NIM (Kimi-K3 2.8T)"),
            (ModelTier.PRO_FALLBACK_2.value, "FALLBACK_2", "Nvidia NIM (GLM-5.3 753B)"),
            (ModelTier.PRO_FALLBACK_3.value, "FALLBACK_3", "Cloudflare (Llama 3.3 70B)")
        ]
    return [(target_model, "PRIMARY", target_model)]

def generate_completion_sync(model: str, messages: list, **kwargs) -> str:
    cascade = _get_cascade_sequence(model)

    # Crucial Deep Research Precaution: Cap tokens to prevent draining unbilled limits
    if "max_tokens" not in kwargs:
        kwargs["max_tokens"] = 2048

    for model_str, tier, name in cascade:
        kwargs = _apply_provider_kwargs(kwargs, model_str, tier_level=tier)
        try:
            print(f"\n📡 Sending request to {name}...")
            response = litellm.completion(
                model=model_str,
                messages=messages,
                drop_params=True,
                timeout=45,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            logger.warning(f"{name} failed: {e}")
            continue

    error_msg = "FATAL ERROR: All 4 Titan fallbacks exhausted."
    print(f"❌ {error_msg}")
    raise RuntimeError(error_msg)

async def generate_completion_async(model: str, messages: list, **kwargs) -> str:
    cascade = _get_cascade_sequence(model)

    if "max_tokens" not in kwargs:
        kwargs["max_tokens"] = 2048

    for model_str, tier, name in cascade:
        kwargs = _apply_provider_kwargs(kwargs, model_str, tier_level=tier)
        try:
            logger.info(f"Async request to {name}...")
            response = await litellm.acompletion(
                model=model_str,
                messages=messages,
                drop_params=True,
                timeout=45,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Async {name} failed: {e}")
            continue

    raise RuntimeError("Async FATAL ERROR: All 4 Titan fallbacks exhausted.")
