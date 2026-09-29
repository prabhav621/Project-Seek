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
        # --- ALGORITHMIC VECTOR PICKER ---
        print("🧠 Curating Forge using Vector Similarity...")
        
        # 1. Get user's top 3 interests by weight
        top_interests = (await db.execute(
            select(InterestVector).order_by(InterestVector.weight.desc()).limit(3)
        )).scalars().all()

        items = []
        if top_interests:
            seen_ids = set()
            allocations = [2, 2, 1] # Diversity split: 2 items for Top Interest, 2 for #2, 1 for #3
            
            for i, interest in enumerate(top_interests):
                limit = allocations[i] if i < len(allocations) else 1
                
                # Filter out items already selected in this loop
                base_query = select(ContentItem).filter(ContentItem.processed == False)
                if seen_ids:
                    base_query = base_query.filter(~ContentItem.id.in_(seen_ids))
                    
                # Use pgvector cosine distance to find the mathematically closest items
                stmt = base_query.order_by(ContentItem.embedding.cosine_distance(interest.embedding)).limit(limit)
                
                matched_items = (await db.execute(stmt)).scalars().all()
                for item in matched_items:
                    items.append(item)
                    seen_ids.add(item.id)
                    
            # If we didn't find 5 items (small backlog), fill the rest chronologically
            if len(items) < 5:
                needed = 5 - len(items)
                base_query = select(ContentItem).filter(ContentItem.processed == False)
                if seen_ids:
                    base_query = base_query.filter(~ContentItem.id.in_(seen_ids))
                
                fill_items = (await db.execute(base_query.order_by(ContentItem.ingested_at.desc()).limit(needed))).scalars().all()
                items.extend(fill_items)
        else:
            # Fallback if no interests exist yet
            items = (await db.execute(select(ContentItem).filter(ContentItem.processed == False).order_by(ContentItem.ingested_at.desc()).limit(5))).scalars().all()

        if not items:
            print("No unprocessed content items found, grabbing latest 5.")
            items = (await db.execute(select(ContentItem).order_by(ContentItem.ingested_at.desc()).limit(5))).scalars().all()
            if not items:
                print("No content at all in DB.")
                return
        # ---------------------------------

        try:
            # 1. Deep Kata
            dk_item = items[0]
            dk_domain = top_interests[0].domain if top_interests else "Technology"
            print(f"Generating Deep Kata...")
            dk = generate_deep_kata(dk_item.raw_text[:3000], dk_domain)
            db.add(DailyItem(
                content_id=dk_item.id, item_type='deep_kata',
                embedding=dk_item.embedding,
                title=dk.title, context=dk.context, crisis=dk.crisis,
                architecture=dk.architecture, kata_question=dk.kata_question,
                mirror_question=dk.mirror_question, domains=[dk_domain],
                suggestion_url=dk_item.source_url
            ))

            # 2. Quick Katas
            for i, qk_item in enumerate(items[1:3]):
                print(f"Generating Quick Kata...")
                qk_domain = top_interests[i].domain if len(top_interests) > i else dk_domain
                qk = generate_quick_kata(qk_item.raw_text[:3000], qk_domain)
                db.add(DailyItem(
                    content_id=qk_item.id, item_type='quick_kata',
                    embedding=qk_item.embedding,
                    title=qk.title, context=qk.context, kata_question=qk.kata_question,
                    domains=[qk_domain],
                    suggestion_url=qk_item.source_url
                ))

            # 3. Aphorism
            aph_item = items[3] if len(items) > 3 else items[0]
            aph_domain = top_interests[-1].domain if top_interests else "Startups"
            print("Generating Aphorism...")
            aph = generate_aphorism(aph_domain)
            db.add(DailyItem(
                content_id=aph_item.id, item_type='aphorism',
                embedding=aph_item.embedding,
                quote_text=aph.quote_text, quote_author=aph.quote_author,
                quote_context=aph.quote_context
            ))

            # 4. Inversion
            inv_item = items[4] if len(items) > 4 else items[0]
            inv_domain = top_interests[0].domain if top_interests else "Product Development"
            print("Generating Inversion...")
            inv = generate_inversion_prompt(inv_domain)
            db.add(DailyItem(
                content_id=inv_item.id, item_type='inversion_prompt',
                embedding=inv_item.embedding,
                inversion_prompt=inv.inversion_prompt
            ))

            # 5. Current Affairs (Curated Suggestion)
            try:
                print("Fetching Current Affairs...")
                # Get top interest domain
                top_domain = (await db.execute(select(InterestVector).order_by(InterestVector.weight.desc()).limit(1))).scalars().first()
                if top_domain:
                    domain_name = top_domain.domain
                    print(f"Top domain for news: {domain_name}")
                    
                    from duckduckgo_search import AsyncDDGS
                    ddgs = AsyncDDGS()
                    news_results = await ddgs.news(domain_name, max_results=1)
                    
                    if news_results:
                        news = news_results[0]
                        news_title = news.get('title', '')
                        news_url = news.get('url', '')
                        news_snippet = news.get('body', '')
                        
                        print(f"Found news: {news_title}")
                        
                        # Generate the hook
                        from src.synthesis.suggestion_curator import generate_suggestion_hook
                        # Pass the title + snippet for a better hook
                        context = f"{news_title} - {news_snippet}"
                        hook_res = generate_suggestion_hook(context, domain_name)
                        
                        db.add(DailyItem(
                            content_id=None,
                            item_type='curated_suggestion',
                            title=news_title,
                            suggestion_url=news_url,
                            suggestion_hook=hook_res.suggestion_hook,
                            domains=[domain_name]
                        ))
            except Exception as e:
                print(f"Skipping Current Affairs due to error: {e}")

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
