from datetime import datetime
from typing import List
from ..db.models import DailyItem

def format_daily_forge(items: List[DailyItem], date: datetime = None) -> str:
    if date is None:
        date = datetime.now()
    
    date_str = date.strftime("%B %d, %Y")
    
    forge_parts = [
        f"🔥 SEEK DAILY FORGE — {date_str}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    # Sort items by type if needed or just extract them.
    # The output format dictates: Aphorism, Deep Kata, Quick Kata 1, Quick Kata 2, Inversion Prompt, Curated Suggestion.
    aphorism = next((i for i in items if i.item_type == "aphorism"), None)
    deep_kata = next((i for i in items if i.item_type == "deep_kata"), None)
    quick_katas = [i for i in items if i.item_type == "quick_kata"]
    inversion_prompt = next((i for i in items if i.item_type == "inversion_prompt"), None)
    curated_suggestion = next((i for i in items if i.item_type == "curated_suggestion"), None)

    if aphorism:
        forge_parts.append("📜 PHILOSOPHER'S STONE")
        forge_parts.append(f"\"{aphorism.quote_text}\"")
        forge_parts.append(f"— {aphorism.quote_author}\n")
        if aphorism.quote_context:
            forge_parts.append(f"→ For you: {aphorism.quote_context}\n")
        forge_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if deep_kata:
        forge_parts.append(f"🧠 DEEP KATA — \"{deep_kata.title}\"")
        if deep_kata.context:
            forge_parts.append(f"📍 {deep_kata.context}")
        if deep_kata.crisis:
            forge_parts.append(f"🔥 {deep_kata.crisis}")
        if deep_kata.architecture:
            forge_parts.append(f"🏗️ {deep_kata.architecture}")
        if deep_kata.kata_question:
            forge_parts.append(f"⚔️ KATA: {deep_kata.kata_question}\n")
        forge_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    for idx, quick_kata in enumerate(quick_katas, start=1):
        forge_parts.append(f"⚡ QUICK KATA #{idx} — \"{quick_kata.title}\"")
        if quick_kata.context:
            forge_parts.append(f"{quick_kata.context}")
        if quick_kata.kata_question:
            forge_parts.append(f"⚔️ {quick_kata.kata_question}\n")
    
    if quick_katas:
        forge_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if inversion_prompt:
        forge_parts.append("🪞 DEVIL'S ADVOCATE")
        if inversion_prompt.inversion_prompt:
            forge_parts.append(f"{inversion_prompt.inversion_prompt}\n")
        forge_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if curated_suggestion:
        forge_parts.append("🔗 TODAY'S RABBIT HOLE")
        forge_parts.append(f"▶️ \"{curated_suggestion.title}\"")
        if curated_suggestion.suggestion_url:
            forge_parts.append(f"[{curated_suggestion.suggestion_url}]")
        if curated_suggestion.suggestion_hook:
            forge_parts.append(f"↳ {curated_suggestion.suggestion_hook}\n")
        forge_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    forge_parts.append("Reply with your Kata answers, or react 👍 to\nmark as read. Ask any question to start a\nSeek Chat session. 🧠")

    return "\n".join(forge_parts)
