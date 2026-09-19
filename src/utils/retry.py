import time
import logging
import asyncio
from functools import wraps
from src.utils.rate_limit import get_limiter_for_model
from src.config import ModelTier
from src.utils.llm_client import generate_completion, generate_embedding

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

async def generate_content_async_with_retry(client, **kwargs):
    model = kwargs.get("model", ModelTier.FLASH.value)
    contents = kwargs.get("contents", "")
    
    limiter = get_limiter_for_model_string(model)
    await limiter.acquire()
    
    text = await generate_completion(model=model, contents=contents)
    return DummyResponse(text)

async def embed_content_async_with_retry(client, **kwargs):
    model = kwargs.get("model", ModelTier.EMBEDDING.value)
    content = kwargs.get("content", "")
    if "contents" in kwargs and not content:
        content = kwargs["contents"]
        
    limiter = get_limiter_for_model_string(model)
    await limiter.acquire()
    
    # Handle single string or list of strings
    if isinstance(content, str):
        content = [content]
        
    vecs = await generate_embedding(model=model, inputs=content)
    return DummyEmbeddingResponse(vecs)

def generate_content_with_retry(client, **kwargs):
    raise NotImplementedError("Use async generate_content_async_with_retry")

def embed_content_with_retry(client, **kwargs):
    raise NotImplementedError("Use async embed_content_async_with_retry")

