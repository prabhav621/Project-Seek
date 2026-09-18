import time
import logging
import asyncio
from functools import wraps
from google.genai.errors import APIError
from src.utils.rate_limit import get_limiter_for_model
from src.config import ModelTier

logger = logging.getLogger(__name__)

def get_limiter_for_model_string(model_name: str):
    if not model_name:
        return get_limiter_for_model(ModelTier.FLASH)
    model_name = model_name.lower()
    if "pro" in model_name:
        return get_limiter_for_model(ModelTier.PRO)
    elif "flash-lite" in model_name:
        return get_limiter_for_model(ModelTier.FLASH_LITE)
    elif "flash" in model_name:
        return get_limiter_for_model(ModelTier.FLASH)
    elif "embedding" in model_name:
        return get_limiter_for_model(ModelTier.EMBEDDING)
    return get_limiter_for_model(ModelTier.FLASH)

def with_retry(max_retries=3, initial_delay=2.0):
    """Decorator to retry a synchronous or asynchronous function."""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                delay = initial_delay
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except APIError as e:
                        status = getattr(e, 'code', None)
                        if status in (429, 500, 503) or status is None:
                            if attempt == max_retries:
                                logger.error(f"Failed after {max_retries} retries: {e}")
                                raise
                            logger.warning(f"API Error {status}. Retrying in {delay} seconds (attempt {attempt+1}/{max_retries})...")
                            await asyncio.sleep(delay)
                            delay *= 2
                        else:
                            raise
                    except TimeoutError as e:
                        if attempt == max_retries:
                            raise
                        logger.warning(f"Timeout Error. Retrying in {delay} seconds (attempt {attempt+1}/{max_retries})...")
                        await asyncio.sleep(delay)
                        delay *= 2
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                delay = initial_delay
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except APIError as e:
                        status = getattr(e, 'code', None)
                        if status in (429, 500, 503) or status is None:
                            if attempt == max_retries:
                                logger.error(f"Failed after {max_retries} retries: {e}")
                                raise
                            logger.warning(f"API Error {status}. Retrying in {delay} seconds (attempt {attempt+1}/{max_retries})...")
                            time.sleep(delay)
                            delay *= 2
                        else:
                            raise
                    except TimeoutError as e:
                        if attempt == max_retries:
                            raise
                        logger.warning(f"Timeout Error. Retrying in {delay} seconds (attempt {attempt+1}/{max_retries})...")
                        time.sleep(delay)
                        delay *= 2
            return sync_wrapper
    return decorator

@with_retry(max_retries=3, initial_delay=2.0)
def generate_content_with_retry(client, **kwargs):
    return client.models.generate_content(**kwargs)

@with_retry(max_retries=3, initial_delay=2.0)
def embed_content_with_retry(client, **kwargs):
    return client.models.embed_content(**kwargs)

@with_retry(max_retries=3, initial_delay=2.0)
async def generate_content_async_with_retry(client, **kwargs):
    limiter = get_limiter_for_model_string(kwargs.get("model", ""))
    await limiter.acquire()
    return await client.aio.models.generate_content(**kwargs)

@with_retry(max_retries=3, initial_delay=2.0)
async def embed_content_async_with_retry(client, **kwargs):
    limiter = get_limiter_for_model_string(kwargs.get("model", ""))
    await limiter.acquire()
    return await client.aio.models.embed_content(**kwargs)
