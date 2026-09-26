import litellm
from src.config import settings, ModelTier
from src.utils.llm_client import _get_cascade_sequence, _apply_provider_kwargs

def test_all_matrix_nodes():
    print("🧪 SEEK ENGINE: 3-TITAN SOVEREIGN MATRIX DIAGNOSTIC")
    print("=" * 60)

    # Get the full fallback cascade
    cascade = _get_cascade_sequence(ModelTier.PRO_PRIMARY.value)
    messages = [{"role": "user", "content": "Reply with exactly: 'Acknowledged'."}]

    success_count = 0
    for model_str, tier, name in cascade:
        print(f"\n[ TESTING ] {name} ...")

        kwargs = _apply_provider_kwargs({"max_tokens": 50}, model_str, tier)

        try:
            res = litellm.completion(
                model=model_str,
                messages=messages,
                drop_params=True,
                **kwargs
            )
            print(f"✅ SUCCESS | Node is ONLINE")
            success_count += 1
        except Exception as e:
            print(f"❌ FAILED  | Error: {e}")

    # Also test the Gemini FLASH tier used for tagging/analysis
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
        print(f"❌ FAILED  | Error: {e}")

    total = len(cascade) + 1  # +1 for Gemini
    print("\n" + "=" * 60)
    print(f"🎯 MATRIX DIAGNOSTIC COMPLETE: {success_count}/{total} Nodes Online")

    if success_count == total:
        print("🔥 ALL SYSTEMS OPERATIONAL. The Sovereign Matrix is fully armed.")
    elif success_count > 0:
        print("💡 The Waterfall router is viable and will use the online nodes.")
    else:
        print("⚠️ FATAL: All nodes offline. Check your API keys in .env.")

if __name__ == "__main__":
    test_all_matrix_nodes()
