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
        # Find all ContentItems that don't have a corresponding NeutralBrick
        query = select(ContentItem).outerjoin(
            NeutralBrick, ContentItem.id == NeutralBrick.source_content_id
        ).filter(NeutralBrick.id == None)
        
        items_to_process = (await db.execute(query)).scalars().all()
        
        total_items = len(items_to_process)
        print(f"Found {total_items} legacy items needing Neutral Bricks.")
        
        for idx, item in enumerate(items_to_process, 1):
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
            
            # Rate Limiting: Sleep to ensure we don't trip free tier limits
            # 300 links * 15 seconds = 1.25 hours
            print("  -> Sleeping 15 seconds to respect rate limits...")
            time.sleep(15)
            
    print("Backfill Complete!")

if __name__ == "__main__":
    asyncio.run(run_backfill())
