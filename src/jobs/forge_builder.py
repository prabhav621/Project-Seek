import asyncio
import sys
from pathlib import Path
from datetime import datetime

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from src.db.session import SessionLocal
from sqlalchemy import select
from src.db.models import ContentItem, DailyItem, InterestVector
from src.synthesis.kata_generator import generate_deep_kata, generate_quick_kata
from src.synthesis.aphorism_generator import generate_aphorism
from src.synthesis.inversion_generator import generate_inversion_prompt

async def build_and_send_forge():
    print("🔨 Building the Daily Forge...")
    async with SessionLocal() as db:
        # Find 5 recent unprocessed items
        items = (await db.execute(select(ContentItem).filter(ContentItem.processed == False).order_by(ContentItem.ingested_at.desc()).limit(5))).scalars().all()
        
        if not items:
            print("No unprocessed content items found, grabbing latest 5.")
            items = (await db.execute(select(ContentItem).order_by(ContentItem.ingested_at.desc()).limit(5))).scalars().all()
            if not items:
                print("No content at all in DB.")
                return

        try:
            # 1. Deep Kata
            dk_item = items[0]
            print(f"Generating Deep Kata...")
            dk = generate_deep_kata(dk_item.raw_text[:3000], "Curated Topic")
            db.add(DailyItem(
                content_id=dk_item.id, item_type='deep_kata',
                title=dk.title, context=dk.context, crisis=dk.crisis,
                architecture=dk.architecture, kata_question=dk.kata_question,
                mirror_question=dk.mirror_question, domains=["Curated Topic"]
            ))

            # 2. Quick Katas
            for qk_item in items[1:3]:
                print(f"Generating Quick Kata...")
                qk = generate_quick_kata(qk_item.raw_text[:3000], "Curated Topic")
                db.add(DailyItem(
                    content_id=qk_item.id, item_type='quick_kata',
                    title=qk.title, context=qk.context, kata_question=qk.kata_question,
                    domains=["Curated Topic"]
                ))

            # 3. Aphorism
            aph_item = items[3] if len(items) > 3 else items[0]
            print("Generating Aphorism...")
            aph = generate_aphorism(aph_item.raw_text[:3000])
            db.add(DailyItem(
                content_id=aph_item.id, item_type='aphorism',
                quote_text=aph.quote_text, quote_author=aph.author,
                quote_context=aph.philosophical_context
            ))

            # 4. Inversion
            inv_item = items[4] if len(items) > 4 else items[0]
            print("Generating Inversion...")
            inv = generate_inversion_prompt(inv_item.raw_text[:3000])
            db.add(DailyItem(
                content_id=inv_item.id, item_type='inversion_prompt',
                inversion_prompt=inv.inversion_prompt
            ))

            # Mark processed
            for item in items:
                item.processed = True
            
            await db.commit()
            print("Successfully populated DailyItems in DB.")
            
        except Exception as e:
            print(f"Error building forge: {e}")
            await db.rollback()
            return
            
    print("Sending Forge to Telegram...")
    from src.jobs.daily_forge import send_forge
    # Since daily_forge is completely async
    await send_forge()

if __name__ == '__main__':
    asyncio.run(build_and_send_forge())
