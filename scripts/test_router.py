import sys
import asyncio
import json
from pathlib import Path

# Add project root to path so we can import src modules
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from src.config import MODEL_POOLS, Capability, settings
import litellm
from pydantic import BaseModel

class DummyBrick(BaseModel):
    core_thesis: str
    key_mechanics: str
    critical_pointers: list[str]

def get_api_key(model_id: str) -> str:
    if "openrouter" in model_id: return settings.openrouter_api_key
    if "nvidia" in model_id: return settings.nvidia_api_key
    if "gemini" in model_id: return settings.gemini_api_key
    return settings.cloudflare_api_key

async def test_all_models():
    # Fetch the exact models currently in your FAST_CREATIVE pool
    models = MODEL_POOLS.get(Capability.FAST_CREATIVE, [])
    print(f"Testing {len(models)} models in the FAST_CREATIVE pool...\n")
    
    # A tiny dummy article to process
    dummy_text = "The rapid advancements in AI have fundamentally changed SaaS pricing. Companies are moving from per-seat pricing to consumption-based models."
    
    system_prompt = "OUTPUT STRICTLY A RAW JSON DICTIONARY with keys: 'core_thesis' (string), 'key_mechanics' (string), and 'critical_pointers' (list of strings)."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Extract a Neutral Brick from the following text:\n\n{dummy_text}"}
    ]
    
    for model in models:
        print(f"==================================================")
        print(f"🚀 TESTING MODEL: {model}")
        print(f"==================================================")
        
        kwargs = {"api_key": get_api_key(model)}
        
        # Apply the exact logic used in strategy_generator.py
        if "cloudflare" not in model:
            kwargs["response_format"] = DummyBrick
        else:
            kwargs["drop_params"] = True
            
        try:
            # Force litellm to not print massive debug logs to keep our console clean
            litellm.suppress_debug_info = True 
            
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                **kwargs
            )
            content = response.choices[0].message.content
            print(f"✅ SUCCESS!")
            print(f"RAW OUTPUT:\n{content}\n")
            
            # Test how our JSON parser handles it
            if isinstance(content, str):
                content_clean = content.strip()
                if content_clean.startswith("```json"): content_clean = content_clean[7:]
                elif content_clean.startswith("```"): content_clean = content_clean[3:]
                if content_clean.endswith("```"): content_clean = content_clean[:-3]
                content_clean = content_clean.strip()
                
                try:
                    parsed = json.loads(content_clean)
                    print(f"🧩 JSON PARSING: SUCCESS")
                except json.JSONDecodeError:
                    import re
                    match = re.search(r'\{.*\}', content_clean, re.DOTALL)
                    if match:
                        print(f"🧩 JSON PARSING: SUCCESS (via Regex Fallback)")
                    else:
                        print(f"❌ JSON PARSING: FAILED. Output is not valid JSON.")
        
        except Exception as e:
            print(f"❌ ERROR: {type(e).__name__}")
            print(f"MESSAGE: {str(e)}\n")

if __name__ == "__main__":
    asyncio.run(test_all_models())
