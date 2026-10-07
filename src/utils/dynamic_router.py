import requests
import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

_cached_reasoning_models = []
_cached_flash_models = []

def _fetch_openrouter_free_models() -> List[Dict]:
    """Fetches all 100% free models from OpenRouter."""
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=8)
        if resp.status_code != 200:
            return []
        
        models = resp.json().get("data", [])
        free_models = []
        for m in models:
            pricing = m.get("pricing", {})
            model_id = m.get("id", "")
            # Verify 0 cost or explicit :free tag
            if (pricing.get("prompt") == "0" and pricing.get("completion") == "0") or model_id.endswith(":free"):
                text_to_search = f"{model_id} {m.get('name', '')}".lower()
                
                # Regex to extract Trillions (t) or Billions (b)
                t_match = re.search(r'([\d\.]+)\s*t\b', text_to_search)
                b_match = re.search(r'([\d\.]+)\s*b\b', text_to_search)
                
                params = 0
                if t_match:
                    params = float(t_match.group(1)) * 1000
                elif b_match:
                    params = float(b_match.group(1))
                    
                free_models.append({
                    "id": model_id,
                    "name": m.get("name", model_id),
                    "params": params
                })
        return free_models
    except Exception as e:
        logger.warning(f"Failed to fetch OpenRouter free models: {e}")
        return []

def get_top_free_reasoning_models(limit: int = 2) -> List[Dict]:
    """
    Fetches free models with >= 70B parameters or known reasoning models (e.g. DeepSeek R1).
    """
    global _cached_reasoning_models
    if _cached_reasoning_models:
        return _cached_reasoning_models
        
    models = _fetch_openrouter_free_models()
    reasoning_candidates = []
    
    for m in models:
        m_id = m["id"].lower()
        # Explicit priority for reasoning or >= 70B
        if "r1" in m_id or "reasoning" in m_id or m["params"] >= 70:
            reasoning_candidates.append(m)
            
    # Sort descending by parameter count
    reasoning_candidates.sort(key=lambda x: x["params"], reverse=True)
    _cached_reasoning_models = reasoning_candidates[:limit]
    
    if not _cached_reasoning_models:
        # Static resilient fallbacks
        _cached_reasoning_models = [
            {"id": "deepseek/deepseek-r1:free", "name": "DeepSeek R1 (Free)", "params": 671},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B (Free)", "params": 70}
        ]
        
    return _cached_reasoning_models

def get_top_free_flash_models(limit: int = 2) -> List[Dict]:
    """
    Fetches lightweight, fast free models (< 70B parameters) for quick extraction and chat.
    """
    global _cached_flash_models
    if _cached_flash_models:
        return _cached_flash_models
        
    models = _fetch_openrouter_free_models()
    flash_candidates = []
    
    for m in models:
        # Lightweight models between 1B and 69B
        if 0 < m["params"] < 70 or "flash" in m["id"].lower() or "8b" in m["id"].lower():
            flash_candidates.append(m)
            
    # Prefer popular fast architectures (Gemini, Llama 8B, Qwen)
    flash_candidates.sort(key=lambda x: (
        1 if "flash" in x["id"].lower() else (
            2 if "llama" in x["id"].lower() else 3
        )
    ))
    _cached_flash_models = flash_candidates[:limit]
    
    if not _cached_flash_models:
        # Static resilient fallbacks
        _cached_flash_models = [
            {"id": "meta-llama/llama-3.1-8b-instruct:free", "name": "Llama 3.1 8B (Free)", "params": 8},
            {"id": "google/gemini-2.0-flash-exp:free", "name": "Gemini 2.0 Flash (Free)", "params": 0}
        ]
        
    return _cached_flash_models

# Alias for legacy compatibility
get_top_free_models = get_top_free_reasoning_models
