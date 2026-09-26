from src.config import ModelTier
from src.utils.llm_client import generate_completion_sync

def test_waterfall():
    print("🧪 SEEK ENGINE: 5-TITAN LLM WATERFALL TEST")
    print("=" * 50)
    
    messages = [{"role": "user", "content": "Reply with only the word 'Acknowledged'."}]
    
    try:
        res = generate_completion_sync(ModelTier.PRO_PRIMARY.value, messages)
        print(f"✅ SUCCESS | Response: {res.strip()}")
    except Exception as e:
        print(f"❌ FINAL FAILURE: {e}")

if __name__ == "__main__":
    test_waterfall()
