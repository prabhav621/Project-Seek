import litellm
from src.config import settings, ModelTier
from src.utils.llm_client import _get_cascade_sequence, _apply_provider_kwargs

def test_all_matrix_nodes():
    print("🧪 SEEK ENGINE: DIAGNOSTIC MATRIX TEST")
    print("=" * 60)
    
    # Get the 5-tier fallback list
    cascade = _get_cascade_sequence(ModelTier.PRO_PRIMARY.value)
    messages = [{"role": "user", "content": "Reply with exactly: 'Acknowledged'."}]
    
    success_count = 0
    for model_str, tier, name in cascade:
        print(f"\n[ TESTING ] {name} ...")
        
        # Apply the specific api_base and api_key for this node
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
            # We catch the exception to allow testing the rest of the matrix
            print(f"❌ FAILED  | Error: {e}")

    print("\n" + "=" * 60)
    print(f"🎯 MATRIX DIAGNOSTIC COMPLETE: {success_count}/{len(cascade)} Nodes Online")
    
    if success_count > 0:
        print("💡 The Waterfall router is viable and will automatically use the online nodes.")
    else:
        print("⚠️ FATAL: All nodes offline. Check your API keys in .env.")

if __name__ == "__main__":
    test_all_matrix_nodes()
