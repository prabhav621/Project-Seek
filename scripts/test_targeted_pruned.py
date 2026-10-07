import sys
import asyncio
import time
from pathlib import Path

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from src.utils.llm_client import _apply_provider_kwargs
import litellm

models_to_test = [
    ("nvidia_nim/meta/llama-3.3-70b-instruct", 35, "NVIDIA NIM (Llama 3.3 70B)", True),
    ("openrouter/anthropic/claude-sonnet-4.5", 30, "OpenRouter (Claude Sonnet 4.5)", True),
    ("cloudflare/@cf/meta/llama-3.3-70b-instruct-fp8-fast", 25, "Cloudflare (Llama 3.3 70B FP8)", True),
    ("cloudflare/@cf/meta/llama-3.1-8b-instruct", 15, "Cloudflare (Llama 3.1 8B)", False)
]

async def test():
    print("\n" + "="*50)
    print("🎯 TARGETED TEST: VERIFYING REPLACEMENT NODES")
    print("="*50)
    
    prompt = "Explain in 1 concise sentence why distribution beats product."
    messages = [
        {"role": "system", "content": "You are a concise strategic advisor."},
        {"role": "user", "content": prompt}
    ]
    
    for slug, timeout, label, is_pro in models_to_test:
        print(f"\n--------------------------------------------------")
        print(f"Testing: {label}")
        print(f"Slug: {slug} [Timeout: {timeout}s]")
        
        kwargs = {
            "max_tokens": 1024 if not is_pro else 2048,
            "temperature": 0.7 if is_pro else 0.2,
            "timeout": timeout,
            "drop_params": True
        }
        call_kwargs = _apply_provider_kwargs(kwargs, slug)
        
        start = time.time()
        try:
            resp = await litellm.acompletion(model=slug, messages=messages, **call_kwargs)
            elapsed = round(time.time() - start, 2)
            content = resp.choices[0].message.content.strip()
            print(f"✅ SUCCESS ({elapsed}s)")
            print(f"Output: {content[:200]}...")
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            print(f"❌ FAILED ({elapsed}s)")
            print(f"Error: {e}")
            
    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(test())
