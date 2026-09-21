import time
import logging
import asyncio
from functools import wraps
from src.utils.rate_limit import get_limiter_for_model
from src.config import ModelTier
from src.utils.llm_client import generate_completion, generate_embedding, generate_completion_sync

logger = logging.getLogger(__name__)


def get_limiter_for_model_string(model_name: str):
    if not model_name:
        return get_limiter_for_model(ModelTier.FLASH)
    model_name = model_name.lower()
    if "nvidia" in model_name or "github" in model_name:
        return get_limiter_for_model(ModelTier.PRO)
    elif "groq" in model_name:
        return get_limiter_for_model(ModelTier.FLASH_LITE)
    elif "gemini" in model_name:
        if "embedding" in model_name:
            return get_limiter_for_model(ModelTier.EMBEDDING)
        return get_limiter_for_model(ModelTier.FLASH)
    return get_limiter_for_model(ModelTier.FLASH)


# ─── Adapter classes ──────────────────────────
# These mimic the Google genai SDK response shape so that existing
# callers (e.g. `response.text`, `response.embeddings[0].values`)
# continue to work without modification.

class DummyResponse:
    def __init__(self, text):
        self.text = text


class DummyEmbedding:
    def __init__(self, values):
        self.values = values


class DummyEmbeddingResponse:
    def __init__(self, vecs):
        self.embeddings = [DummyEmbedding(v) for v in vecs]


# ─── Retry decorator ─────────────────────────

def with_retry(max_retries=3, initial_delay=2.0):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    status = getattr(e, 'status_code', None)
                    if status in (429, 500, 502, 503) or "timeout" in str(e).lower() or attempt < max_retries:
                        if attempt == max_retries:
                            logger.error(f"Failed after {max_retries} retries: {e}")
                            raise
                        logger.warning(f"API Error {status}. Retrying in {delay} seconds (attempt {attempt+1}/{max_retries})...")
                        await asyncio.sleep(delay)
                        delay *= 2
                    else:
                        raise
        return async_wrapper
    return decorator


def _extract_config(kwargs):
    """Extract temperature, system_instruction, and json_mode from a Google genai config object."""
    config = kwargs.get("config", None)
    temperature = 0.7
    system_instruction = None
    json_mode = False

    if config:
        temperature = getattr(config, 'temperature', 0.7) or 0.7
        system_instruction = getattr(config, 'system_instruction', None)
        if getattr(config, 'response_mime_type', '') == 'application/json':
            json_mode = True

    return temperature, system_instruction, json_mode


# ─── ASYNC functions (ingestion pipeline) ─────

@with_retry(max_retries=3, initial_delay=2.0)
async def generate_content_async_with_retry(client, **kwargs):
    model = kwargs.get("model", ModelTier.FLASH.value)
    contents = kwargs.get("contents", "")

    limiter = get_limiter_for_model_string(model)
    await limiter.acquire()

    text = await generate_completion(model=model, contents=contents)
    return DummyResponse(text)


@with_retry(max_retries=3, initial_delay=2.0)
async def embed_content_async_with_retry(client, **kwargs):
    model = kwargs.get("model", ModelTier.EMBEDDING.value)
    content = kwargs.get("content", "")
    if "contents" in kwargs and not content:
        content = kwargs["contents"]

    # Extract output_dimensionality from config dict if present
    config = kwargs.get("config", {})
    dimensions = None
    if isinstance(config, dict):
        dimensions = config.get("output_dimensionality")

    limiter = get_limiter_for_model_string(model)
    await limiter.acquire()

    if isinstance(content, str):
        content = [content]

    vecs = await generate_embedding(model=model, inputs=content, dimensions=dimensions)
    return DummyEmbeddingResponse(vecs)


# ─── SYNC functions (Daily Forge, Reply Analyzer, Seek Chat, etc.) ─────

def generate_content_with_retry(client, max_retries=3, initial_delay=2.0, **kwargs):
    """
    Synchronous LLM call with retry logic. Routes through LiteLLM.
    Falls back to the direct Google SDK for multimodal content (file uploads).
    """
    model = kwargs.get("model", ModelTier.FLASH.value)
    contents = kwargs.get("contents", "")

    # Handle multimodal content (e.g., media.py passing [gemini_file, prompt])
    # LiteLLM cannot handle Google File objects, so fall back to direct SDK
    if isinstance(contents, list) and any(not isinstance(c, str) for c in contents):
        # Strip "gemini/" prefix for direct Google SDK calls
        raw_model = model.replace("gemini/", "") if model.startswith("gemini/") else model
        kwargs["model"] = raw_model
        return client.models.generate_content(**kwargs)

    # Flatten list of strings into a single string
    if isinstance(contents, list):
        contents = "\n".join(str(c) for c in contents)

    temperature, system_instruction, json_mode = _extract_config(kwargs)

    delay = initial_delay
    for attempt in range(max_retries + 1):
        try:
            # Basic sync throttle (can't use async limiter in sync context)
            time.sleep(0.5)
            text = generate_completion_sync(
                model=model,
                contents=contents,
                system_instruction=system_instruction,
                temperature=temperature,
                json_mode=json_mode,
            )
            return DummyResponse(text)
        except Exception as e:
            status = getattr(e, 'status_code', None)
            if status in (429, 500, 502, 503) or "timeout" in str(e).lower():
                if attempt == max_retries:
                    logger.error(f"Sync retry failed after {max_retries} retries: {e}")
                    raise
                logger.warning(f"Sync API Error {status}. Retrying in {delay}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
            else:
                raise


def embed_content_with_retry(client, **kwargs):
    raise NotImplementedError("Use async embed_content_async_with_retry for embeddings")
