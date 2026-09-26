import requests
import re
import logging

logger = logging.getLogger(__name__)

_cached_models = []

def get_top_free_models(limit=3):
    """
    Fetches free models from OpenRouter, extracts their parameter count,
    filters for >= 70B, and sorts them by size descending to find the 'Sweet Spot'.
    """
    global _cached_models
    if _cached_models:
        return _cached_models
        
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        if resp.status_code != 200:
            raise ValueError(f"Failed to fetch models: {resp.status_code}")
            
        models = resp.json().get("data", [])
        free_models = []
        
        for m in models:
            pricing = m.get("pricing", {})
            # Ensure it is completely free
            if pricing.get("prompt") == "0" and pricing.get("completion") == "0":
                
                # Check if it has a `:free` suffix (OpenRouter convention for free endpoints)
                # or is explicitly 0 cost
                model_id = m.get("id", "")
                
                text_to_search = f"{model_id} {m.get('name', '')}".lower()
                
                # Regex to extract Trillions (t) or Billions (b)
                t_match = re.search(r'([\d\.]+)\s*t\b', text_to_search)
                b_match = re.search(r'([\d\.]+)\s*b\b', text_to_search)
                
                params = 0
                if t_match:
                    params = float(t_match.group(1)) * 1000  # Convert to billions
                elif b_match:
                    params = float(b_match.group(1))
                    
                # The Sweet Spot filter: 70B or larger
                if params >= 70:
                    free_models.append({
                        "id": model_id,
                        "name": m.get("name", model_id),
                        "params": params
                    })
        
        # Sort strictly by parameter size (Descending)
        free_models.sort(key=lambda x: x["params"], reverse=True)
        
        # Cache and return the IDs
        _cached_models = free_models[:limit]
        
        if not _cached_models:
            # Absolute fallback if regex fails
            _cached_models = [{"id": "meta-llama/llama-3.1-70b-instruct:free", "name": "Llama 3.1 70B", "params": 70}]
            
        return _cached_models

    except Exception as e:
        logger.warning(f"Dynamic Router Error: {e}")
        return [{"id": "meta-llama/llama-3.1-70b-instruct:free", "name": "Llama 3.1 70B (Static Fallback)", "params": 70}]
