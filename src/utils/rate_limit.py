import aiolimiter
from src.config import ModelTier

# Provider-Specific Rate Limiters
nvidia_limiter = aiolimiter.AsyncLimiter(35, 60)    # NVIDIA NIM allows ~40 RPM
openrouter_limiter = aiolimiter.AsyncLimiter(25, 60) # OpenRouter (Dynamic) limit
google_limiter = aiolimiter.AsyncLimiter(14, 60)    # Google Free Tier limits to 15 RPM
cloudflare_limiter = aiolimiter.AsyncLimiter(50, 60) # Cloudflare Edge limit

def get_limiter_for_model(model_tier: ModelTier):
    if model_tier == ModelTier.PRO_PRIMARY:
        return nvidia_limiter
    elif model_tier == ModelTier.PRO_SAFETY_NET:
        return cloudflare_limiter
    else:
        # Default to Google for FLASH and EMBEDDING
        return google_limiter

