import aiolimiter
from src.config import ModelTier

# EMERGENCY FIX: Rate limits are shared at the PROJECT level.
# We must use a single global token bucket capped at 14 RPM to protect the whole project.
global_limiter = aiolimiter.AsyncLimiter(14, 60)

def get_limiter_for_model(model_tier: ModelTier):
    # All models share the same project-level API limit in the free tier
    return global_limiter
