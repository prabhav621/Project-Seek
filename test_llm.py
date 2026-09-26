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

def test_daily_forge():
    print("\n\n⚒️ SEEK ENGINE: MOCK DAILY FORGE GENERATION")
    print("=" * 60)
    print("Simulating a morning Daily Forge (Deep Kata, Aphorism, Inversion, Quick Kata).")
    print("Testing concurrent rate limit isolation between Nvidia NIM and Gemini.\n")
    
    # 1. Deep Kata (PRO Node)
    print("[STEP 1] Forging Deep Kata (PRO tier: Nvidia/OpenRouter)...")
    kata_messages = [{"role": "user", "content": "Write a 2-sentence philosophical Deep Kata about AI architecture."}]
    start_t = time.time()
    try:
        kata_res = generate_completion_sync(ModelTier.PRO_PRIMARY.value, kata_messages, max_tokens=150)
        print(f"✅ Deep Kata Complete ({time.time() - start_t:.2f}s):\n   {kata_res}")
    except Exception as e:
        print(f"❌ Deep Kata Failed: {e}")

    # 2. Aphorism (PRO Node)
    print("\n[STEP 2] Forging Aphorism (PRO tier)...")
    aphorism_messages = [{"role": "user", "content": "Give me a one-sentence aphorism about resilience."}]
    start_t = time.time()
    try:
        aph_res = generate_completion_sync(ModelTier.PRO_PRIMARY.value, aphorism_messages, max_tokens=50)
        print(f"✅ Aphorism Complete ({time.time() - start_t:.2f}s):\n   {aph_res}")
    except Exception as e:
        print(f"❌ Aphorism Failed: {e}")

    # 3. Quick Kata (FLASH Node - Gemini)
    print("\n[STEP 3] Forging Quick Kata (FLASH tier: Gemini)...")
    qk_messages = [{"role": "user", "content": "Give me a fast summary of quantum mechanics."}]
    start_t = time.time()
    try:
        qk_res = generate_completion_sync(ModelTier.FLASH.value, qk_messages, max_tokens=100)
        print(f"✅ Quick Kata (Gemini) Complete ({time.time() - start_t:.2f}s):\n   {qk_res}")
    except Exception as e:
        print(f"❌ Quick Kata Failed: {e}")

if __name__ == "__main__":
    test_all_matrix_nodes()
    test_daily_forge()
