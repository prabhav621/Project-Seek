import aiolimiter
from src.config import ModelTier

# Set each to 14 requests per 60 seconds (14 RPM)
pro_limiter = aiolimiter.AsyncLimiter(14, 60)
flash_limiter = aiolimiter.AsyncLimiter(14, 60)
flash_lite_limiter = aiolimiter.AsyncLimiter(14, 60)
embed_limiter = aiolimiter.AsyncLimiter(14, 60)

def get_limiter_for_model(model_tier: ModelTier):
    if model_tier == ModelTier.PRO:
        return pro_limiter
    elif model_tier == ModelTier.FLASH:
        return flash_limiter
    elif model_tier == ModelTier.FLASH_LITE:
        return flash_lite_limiter
    elif model_tier == ModelTier.EMBEDDING:
        return embed_limiter
    else:
        return flash_limiter # Default fallback
