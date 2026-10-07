import sys
import asyncio
import time
from pathlib import Path

# Add project root to path
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from src.config import settings, Tier
from src.utils.llm_client import _get_cascade_sequence, _apply_provider_kwargs, generate_completion_async
from src.synthesis.strategy_generator import parse_neutral_brick
import litellm

# Configure logging to console and bot_logs.txt
log_file = root_path / "bot_logs.txt"
def log(msg: str):
    print(msg)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

async def test_endpoint(model_str: str, timeout_sec: int, name: str, prompt: str, is_pro: bool = False):
    log(f"\n--------------------------------------------------")
    log(f"Testing Endpoint: {name}")
    log(f"Slug: {model_str} | Timeout: {timeout_sec}s")
    
    kwargs = {
        "max_tokens": 1024 if not is_pro else 2048,
        "temperature": 0.2 if not is_pro else 0.7,
        "timeout": timeout_sec,
        "drop_params": True
    }
    call_kwargs = _apply_provider_kwargs(kwargs, model_str)
    
    messages = [
        {"role": "system", "content": "You are a concise, high-leverage strategic advisor. Answer cleanly in under 60 words."},
        {"role": "user", "content": prompt}
    ]
    
    start_time = time.time()
    try:
        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            **call_kwargs
        )
        elapsed = round(time.time() - start_time, 2)
        content = response.choices[0].message.content.strip()
        log(f"✅ STATUS: SUCCESS ({elapsed}s)")
        log(f"Sample Output:\n{content[:250]}...\n")
        return True, elapsed, None
    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        err_msg = str(e)
        log(f"❌ STATUS: FAILED ({elapsed}s)")
        log(f"Error Type: {type(e).__name__}")
        log(f"Error Details: {err_msg[:300]}\n")
        return False, elapsed, err_msg

async def run_diagnostics():
    log("\n" + "="*60)
    log("🚀 RUNNING BULLETPROOF UNIFIED ROUTER DIAGNOSTICS")
    log("="*60)
    
    tiers_to_test = [
        (Tier.PRO, "Explain Palantir's ontology moat in 2 sentences.", True),
        (Tier.FLASH, "Summarize: AI pricing is shifting from per-seat to usage metrics.", False),
        (Tier.LITE, "THESIS: AI shifts pricing.\nMECHANICS: Metered API.\nPOINTERS:\n- Metric 1\n- Metric 2", False)
    ]
    
    for tier, test_prompt, is_pro in tiers_to_test:
        log(f"\n{'#'*60}")
        log(f"🔍 EVALUATING TIER: {tier.value.upper()}")
        log(f"{'#'*60}")
        
        cascade = _get_cascade_sequence(tier.value)
        log(f"Configured Fallback Sequence ({len(cascade)} models in chain):")
        for idx, (m_slug, to, label) in enumerate(cascade, 1):
            log(f"  {idx}. {label} -> {m_slug}")
            
        # 1. Test each endpoint individually
        log(f"\n--- Testing Individual Nodes in {tier.value.upper()} ---")
        for m_slug, to, label in cascade:
            await test_endpoint(m_slug, to, label, test_prompt, is_pro=is_pro)
            # Brief breath between API hits
            await asyncio.sleep(1)
            
        # 2. Test End-to-End Fallback Cascade for the Tier
        log(f"\n--- Testing End-to-End Automatic Failover for {tier.value.upper()} ---")
        start_t = time.time()
        try:
            tier_messages = [
                {"role": "system", "content": "You are a concise strategic partner."},
                {"role": "user", "content": test_prompt}
            ]
            result = await generate_completion_async(tier.value, messages=tier_messages)
            elapsed = round(time.time() - start_t, 2)
            log(f"🎯 END-TO-END TIER RESOLUTION: SUCCESS ({elapsed}s)")
            log(f"Resolved Response:\n{result[:200]}...\n")
        except Exception as e:
            elapsed = round(time.time() - start_t, 2)
            log(f"❌ END-TO-END TIER RESOLUTION: FAILED ({elapsed}s)")
            log(f"Cascade Failure: {e}\n")

    log("\n" + "="*60)
    log("🏁 DIAGNOSTICS COMPLETE. Full audit logged to bot_logs.txt")
    log("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
