import time
import logging
from functools import wraps
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

def with_retry(max_retries=3, initial_delay=2.0):
    """Decorator to retry a synchronous function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
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
        return wrapper
    return decorator

@with_retry(max_retries=3, initial_delay=2.0)
def generate_content_with_retry(client, **kwargs):
    return client.models.generate_content(**kwargs)

@with_retry(max_retries=3, initial_delay=2.0)
def embed_content_with_retry(client, **kwargs):
    return client.models.embed_content(**kwargs)
