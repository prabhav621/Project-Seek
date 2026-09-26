import litellm
import time
from src.config import settings, ModelTier
from src.utils.llm_client import _get_cascade_sequence, _apply_provider_kwargs, generate_completion_sync

def test_all_matrix_nodes():
    print("🧪 SEEK ENGINE: 5-SLOT DYNAMIC MATRIX DIAGNOSTIC")
    print("=" * 60)

    # Get the full fallback cascade (this will auto-trigger the Dynamic Router)
    cascade = _get_cascade_sequence(ModelTier.PRO_PRIMARY.value)
    messages = [{"role": "user", "content": "Reply with exactly: 'Acknowledged'."}]

    success_count = 0
    for model_str, timeout_sec, name in cascade:
        print(f"\n[ TESTING ] {name} ... (Timeout: {timeout_sec}s)")

        # Override max_tokens for a fast diagnostic
        kwargs = _apply_provider_kwargs({"max_tokens": 50}, model_str)

        try:
            res = litellm.completion(
                model=model_str,
                messages=messages,
                drop_params=True,
                timeout=timeout_sec,
                **kwargs
            )
            print(f"✅ SUCCESS | Node is ONLINE")
            success_count += 1
        except Exception as e:
            print(f"❌ FAILED  | {e}")

    # Test the Gemini FLASH tier
    print(f"\n[ TESTING ] Gemini Flash Lite (FLASH tier) ...")
    try:
        res = litellm.completion(
            model=ModelTier.FLASH.value,
            messages=messages,
            api_key=settings.gemini_api_key,
            max_tokens=50,
            drop_params=True,
        )
        print(f"✅ SUCCESS | Node is ONLINE")
        success_count += 1
    except Exception as e:
        print(f"❌ FAILED  | {e}")

    total = len(cascade) + 1  # +1 for Gemini
    print("\n" + "=" * 60)
    print(f"🎯 MATRIX DIAGNOSTIC COMPLETE: {success_count}/{total} Nodes Online")

def test_mock_kata():
    print("\n\n🥋 SEEK ENGINE: MOCK KATA GENERATION")
    print("=" * 60)
    print("This tests the pipeline interactions and rate limit isolation.")
    
    # 1. Simulate tagging via Gemini Flash (Fast/Cheap)
    print("\n[STEP 1] Generating Domain Tags using Gemini (FLASH_LITE tier)...")
    tag_messages = [{"role": "user", "content": "Extract 3 tags from this text: 'Apple releases new M4 Macbook Pro with advanced neural engine.' Format as CSV."}]
    start_t = time.time()
    try:
        tag_res = generate_completion_sync(ModelTier.FLASH_LITE.value, tag_messages, max_tokens=20)
        print(f"✅ Gemini Tagging Complete ({time.time() - start_t:.2f}s): {tag_res}")
    except Exception as e:
        print(f"❌ Gemini Tagging Failed: {e}")

    # 2. Simulate Deep Kata generation via PRO Node
    print("\n[STEP 2] Generating Deep Kata using Sovereign Matrix (PRO tier)...")
    kata_messages = [{"role": "user", "content": "Write a 2-sentence philosophical synthesis about silicon and intelligence."}]
    start_t = time.time()
    try:
        # This will hit the waterfall (Nemotron 550B -> OpenRouter -> Cloudflare)
        kata_res = generate_completion_sync(ModelTier.PRO_PRIMARY.value, kata_messages, max_tokens=150)
        print(f"✅ PRO Kata Generation Complete ({time.time() - start_t:.2f}s):\n{kata_res}")
    except Exception as e:
        print(f"❌ PRO Kata Generation Failed: {e}")

if __name__ == "__main__":
    test_all_matrix_nodes()
    test_mock_kata()
