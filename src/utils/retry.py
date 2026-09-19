import time
import logging
import asyncio
from functools import wraps
from src.utils.rate_limit import get_limiter_for_model
from src.config import ModelTier
from src.utils.llm_client import generate_completion, generate_embedding
import litellm

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

class DummyResponse:
    def __init__(self, text):
        self.text = text

class DummyEmbedding:
    def __init__(self, values):
        self.values = values

class DummyEmbeddingResponse:
    def __init__(self, vecs):
        self.embeddings = [DummyEmbedding(v) for v in vecs]

def with_retry(max_retries=3, initial_delay=2.0):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # litellm wraps errors, catching general exception
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
        
    limiter = get_limiter_for_model_string(model)
    await limiter.acquire()
    
    if isinstance(content, str):
        content = [content]
        
    vecs = await generate_embedding(model=model, inputs=content)
    return DummyEmbeddingResponse(vecs)

def generate_content_with_retry(client, **kwargs):
    raise NotImplementedError("Use async generate_content_async_with_retry")

def embed_content_with_retry(client, **kwargs):
    raise NotImplementedError("Use async embed_content_async_with_retry")
