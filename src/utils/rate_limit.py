import aiolimiter
from src.config import ModelTier

# Provider-Specific Rate Limiters
groq_limiter = aiolimiter.AsyncLimiter(28, 60)      # Groq allows 30 RPM
nvidia_limiter = aiolimiter.AsyncLimiter(35, 60)    # NVIDIA NIM allows ~40 RPM
google_limiter = aiolimiter.AsyncLimiter(14, 60)    # Google Free Tier limits to 15 RPM
github_limiter = aiolimiter.AsyncLimiter(10, 60)    # GitHub Models typically strict (10-15 RPM)

def get_limiter_for_model(model_tier: ModelTier):
    if model_tier == ModelTier.PRO:
        return nvidia_limiter
    elif model_tier == ModelTier.PRO_FALLBACK:
        return github_limiter
    elif model_tier == ModelTier.FLASH_LITE:
        return groq_limiter
    else:
        # Default to Google for FLASH and EMBEDDING
        return google_limiter
