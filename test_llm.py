import os
import sys

# Ensure the root directory is in the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import ModelTier
from src.utils.llm_client import generate_completion_sync

def test_router():
    print("==================================================")
    print("🧪 SEEK ENGINE: LLM WATERFALL & ROUTER TEST")
    print("==================================================\n")
    
    tiers = [
        ("PRO", ModelTier.PRO.value),
        ("FLASH", ModelTier.FLASH.value),
        ("FLASH_LITE", ModelTier.FLASH_LITE.value)
    ]
    
    for name, model_string in tiers:
        print(f"📡 Sending request to {name} tier [{model_string}]...")
        try:
            # We use a very low temperature and a simple prompt to save tokens
            res = generate_completion_sync(
                model=model_string,
                contents="Reply with the exact word 'Acknowledged' and nothing else.",
                temperature=0.1
            )
            print(f"✅ SUCCESS | Response: {res.strip()}\n")
        except Exception as e:
            print(f"❌ FATAL ERROR | All fallbacks exhausted. Error: {e}\n")

if __name__ == "__main__":
    test_router()
