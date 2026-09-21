import litellm
import asyncio
import time
from src.config import settings, ModelTier
import os

# Ensure environment variables are loaded for litellm
os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
if settings.groq_api_key:
    os.environ["GROQ_API_KEY"] = settings.groq_api_key
if settings.github_token:
    os.environ["GITHUB_TOKEN"] = settings.github_token
if settings.nvidia_api_key:
    os.environ["NVIDIA_API_KEY"] = settings.nvidia_api_key


def _route_model(model: str, contents: str) -> str:
    """Apply context-overflow routing: if Groq model but text is too large, reroute to Gemini."""
    estimated_tokens = len(contents) / 4
    if "groq" in model and estimated_tokens > 7500:
        return ModelTier.FLASH.value
    return model


# ───────────────────────────────────────────────
#  ASYNC versions (used by ingestion pipeline)
# ───────────────────────────────────────────────

async def generate_completion(model: str, contents: str, fallback: bool = True) -> str:
    target_model = _route_model(model, contents)
    messages = [{"role": "user", "content": contents}]
    
    kwargs = {
        "model": target_model,
        "messages": messages
    }
    if "gemini" in target_model:
        kwargs["api_key"] = settings.gemini_api_key
    elif "groq" in target_model:
        kwargs["api_key"] = settings.groq_api_key
    elif "nvidia" in target_model:
        kwargs["api_key"] = settings.nvidia_api_key
    elif "github" in target_model:
        kwargs["api_key"] = settings.github_token

    try:
        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        if fallback and "nvidia/deepseek" in model:
            print(f"Primary PRO node failed ({e}). Falling back to GitHub Models...")
            response = await litellm.acompletion(
                model=ModelTier.PRO_FALLBACK.value,
                messages=messages
            )
            return response.choices[0].message.content
        raise e


async def generate_embedding(model: str, inputs: list[str]) -> list[list[float]]:
    kwargs = {
        "model": model,
        "input": inputs
    }
    if "gemini" in model:
        kwargs["api_key"] = settings.gemini_api_key
        
    response = await litellm.aembedding(**kwargs)
    return [d["embedding"] for d in response.data]


# ───────────────────────────────────────────────
#  SYNC versions (used by Daily Forge generators,
#  Reply Analyzer, Seek Chat, Media Transcriber)
# ───────────────────────────────────────────────

def generate_completion_sync(
    model: str,
    contents: str,
    system_instruction: str = None,
    temperature: float = 0.7,
    json_mode: bool = False,
    fallback: bool = True,
) -> str:
    """Synchronous LLM call through LiteLLM. Used by all non-ingestion modules."""
    target_model = _route_model(model, contents)

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": contents})

    kwargs = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "gemini" in target_model:
        kwargs["api_key"] = settings.gemini_api_key
    elif "groq" in target_model:
        kwargs["api_key"] = settings.groq_api_key
    elif "nvidia" in target_model:
        kwargs["api_key"] = settings.nvidia_api_key
    elif "github" in target_model:
        kwargs["api_key"] = settings.github_token

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = litellm.completion(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        if fallback and "nvidia/deepseek" in model:
            print(f"Primary PRO node failed ({e}). Falling back to GitHub Models...")
            kwargs["model"] = ModelTier.PRO_FALLBACK.value
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content
        raise e


def generate_chat_sync(
    model: str,
    messages: list,
    system_instruction: str = None,
    temperature: float = 0.7,
    json_mode: bool = False,
) -> str:
    """Synchronous multi-turn chat call. Used by Seek Chat."""
    full_messages = []
    if system_instruction:
        full_messages.append({"role": "system", "content": system_instruction})
    full_messages.extend(messages)

    kwargs = {
        "model": model,
        "messages": full_messages,
        "temperature": temperature,
    }
    
    if "gemini" in model:
        kwargs["api_key"] = settings.gemini_api_key
    elif "groq" in model:
        kwargs["api_key"] = settings.groq_api_key
    elif "nvidia" in model:
        kwargs["api_key"] = settings.nvidia_api_key
    elif "github" in model:
        kwargs["api_key"] = settings.github_token

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = litellm.completion(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        if "nvidia/deepseek" in model:
            print(f"Primary PRO node failed ({e}). Falling back to GitHub Models...")
            kwargs["model"] = ModelTier.PRO_FALLBACK.value
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content
        raise e
