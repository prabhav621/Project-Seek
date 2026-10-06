import sys
import os
import asyncio
import time
from pathlib import Path

# Add project root to path
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from sqlalchemy import select
from src.db.session import SessionLocal
from src.db.models import ContentItem, NeutralBrick
from src.synthesis.strategy_generator import DualLayerContextEngine

async def run_backfill():
    print("Starting Historical Neutral Brick Backfill...")
    engine = DualLayerContextEngine(root_dir=str(root_path))
    
    async with SessionLocal() as db:
        # Fetch ONLY the IDs to avoid SQLAlchemy lazy-loading / MissingGreenlet errors across commits
        query = select(ContentItem.id).outerjoin(
            NeutralBrick, ContentItem.id == NeutralBrick.source_content_id
        ).filter(NeutralBrick.id == None)
        
        item_ids = (await db.execute(query)).scalars().all()
        
        total_items = len(item_ids)
        print(f"Found {total_items} legacy items needing Neutral Bricks.")
        
        for idx, item_id in enumerate(item_ids, 1):
            # Fetch the actual item fresh for this iteration
            item = (await db.execute(select(ContentItem).filter(ContentItem.id == item_id))).scalar_one()
            
            if not item.raw_text:
                print(f"[{idx}/{total_items}] Skipping Item {item.id} - No raw text.")
                continue
                
            print(f"[{idx}/{total_items}] Processing Item {item.id}...")
            
            try:
                # Use FAST_CREATIVE node to extract the brick
                brick_dict = await engine.generate_strategy(item.raw_text[:8000]) 
                
                if brick_dict:
                    new_brick = NeutralBrick(
                        source_content_id=item.id,
                        core_thesis=brick_dict.get('core_thesis', 'N/A'),
                        key_mechanics=brick_dict.get('key_mechanics', 'N/A'),
                        critical_pointers=brick_dict.get('critical_pointers', [])
                    )
                    db.add(new_brick)
                    await db.commit()
                    print(f"  -> Successfully generated and saved Neutral Brick.")
                else:
                    print(f"  -> Failed to generate brick (LLM returned None).")
                    
            except Exception as e:
                print(f"  -> Error processing item: {e}")
                await db.rollback()
            
            # Rate Limiting: await asyncio.sleep instead of time.sleep so we don't block the async loop
            print("  -> Sleeping 15 seconds to respect rate limits...")
            await asyncio.sleep(15)
            
    print("Backfill Complete!")

if __name__ == "__main__":
    asyncio.run(run_backfill())
