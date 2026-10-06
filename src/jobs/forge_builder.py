import asyncio
import sys
from pathlib import Path
import random
from datetime import datetime, timezone

root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from src.db.session import SessionLocal
from sqlalchemy import select
from src.db.models import ContentItem, DailyItem, InterestVector
from src.synthesis.kata_generator import generate_deep_kata, generate_quick_kata
from src.synthesis.aphorism_generator import generate_aphorism
from src.synthesis.inversion_generator import generate_inversion_prompt

async def build_and_send_forge():
    print("💥 Building the Daily Forge...")
    async with SessionLocal() as db:
        # --- ALGORITHMIC VECTOR PICKER (V1.5) ---
        print("🧠 Curating Forge using Entropy & Weighted Lottery...")
        
        all_domains_query = await db.execute(select(InterestVector))
        all_domains = all_domains_query.scalars().all()
        
        if not all_domains:
            print("No interests found in DB.")
            return
            
        now_tz = datetime.now(timezone.utc)
        
        # 1. Apply Entropy (Decay)
        for d in all_domains:
            if d.last_engaged:
                days_idle = (now_tz - d.last_engaged).days
                if days_idle > 7:
                    d.weight = max(0.1, d.weight - d.decay_rate)
                    
        # 2. Slot Allocation Protocol (2-1-1 Rule)
        sorted_domains = sorted(all_domains, key=lambda x: x.weight, reverse=True)
        dk_domain_obj = sorted_domains[0] # The Apex
        
        remaining_domains = sorted_domains[1:] if len(sorted_domains) > 1 else sorted_domains
        weights = [d.weight for d in remaining_domains]
        
        if len(remaining_domains) >= 2:
            qk_domains_obj = random.choices(remaining_domains, weights=weights, k=2)
        else:
            qk_domains_obj = [dk_domain_obj, dk_domain_obj]
            
        used_domains = [dk_domain_obj] + qk_domains_obj
        blind_spots = [d for d in all_domains if d not in used_domains]
        news_domain_obj = random.choice(blind_spots) if blind_spots else dk_domain_obj
        
        top_interests = [dk_domain_obj, qk_domains_obj[0], qk_domains_obj[1], news_domain_obj]

        items = []
        seen_ids = set()
        allocations = [2, 2, 1] # Diversity split: 2 items for DK interest, 2 for QK1, 1 for QK2
        
        for i, interest in enumerate(top_interests[:3]):
            limit = allocations[i] if i < len(allocations) else 1
            
            base_query = select(ContentItem).filter(ContentItem.processed == False)
            if seen_ids:
                base_query = base_query.filter(~ContentItem.id.in_(seen_ids))
                
            stmt = base_query.order_by(ContentItem.embedding.cosine_distance(interest.embedding)).limit(limit)
            
            matched_items = (await db.execute(stmt)).scalars().all()
            for item in matched_items:
                items.append(item)
                seen_ids.add(item.id)
                
        # Fill chronologically if short
        if len(items) < 5:
            needed = 5 - len(items)
            base_query = select(ContentItem).filter(ContentItem.processed == False)
            if seen_ids:
                base_query = base_query.filter(~ContentItem.id.in_(seen_ids))
            fill_items = (await db.execute(base_query.order_by(ContentItem.ingested_at.desc()).limit(needed))).scalars().all()
            items.extend(fill_items)

        if not items:
            print("No unprocessed content items found, grabbing latest 5.")
            items = (await db.execute(select(ContentItem).order_by(ContentItem.ingested_at.desc()).limit(5))).scalars().all()
            if not items:
                print("No content at all in DB.")
                return

        try:
            # 1. Quick Kata (replaces Deep Kata)
            dk_item = items[0]
            dk_domain = top_interests[0].domain
            print(f"Generating Quick Kata for {dk_domain}...")
            qk1 = generate_quick_kata(dk_item.raw_text[:3000], dk_domain)
            db.add(DailyItem(
                content_id=dk_item.id, item_type='quick_kata',
                embedding=dk_item.embedding,
                title=qk1.title, context=qk1.context, kata_question=qk1.kata_question,
                domains=[dk_domain],
                suggestion_url=dk_item.source_url
            ))

            # 2. Quick Katas (only 1 now to make exactly 2 total)
            for i, qk_item in enumerate(items[1:2]):
                qk_domain = top_interests[i+1].domain
                print(f"Generating Quick Kata for {qk_domain}...")
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
            aph_domain = top_interests[1].domain
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
            inv_domain = top_interests[0].domain
            print("Generating Inversion...")
            inv = generate_inversion_prompt(inv_domain)
            db.add(DailyItem(
                content_id=inv_item.id, item_type='inversion_prompt',
                embedding=inv_item.embedding,
                inversion_prompt=inv.inversion_prompt
            ))

            # 5. Current Affairs (Blind Spot via Crawl4AI)
            try:
                domain_name = top_interests[3].domain
                print(f"Fetching Current Affairs for Blind Spot: {domain_name}...")
                
                from duckduckgo_search import AsyncDDGS
                ddgs = AsyncDDGS()
                news_results = await ddgs.news(domain_name, max_results=1)
                
                if news_results:
                    news = news_results[0]
                    news_title = news.get('title', '')
                    news_url = news.get('url', '')
                    news_snippet = news.get('body', '')
                    
                    print(f"Found news: {news_title}")
                    
                    context_text = f"{news_title} - {news_snippet}"
                    
                    try:
                        from crawl4ai import AsyncWebCrawler
                        print(f"Crawling {news_url} for deep context...")
                        async with AsyncWebCrawler(verbose=False) as crawler:
                            result = await crawler.arun(url=news_url)
                            if result.success and result.markdown:
                                context_text = f"Title: {news_title}\n\nContent:\n{result.markdown[:4000]}"
                    except Exception as crawl_e:
                        print(f"Crawl failed, using snippet. Error: {crawl_e}")
                    
                    # Generate the hook
                    from src.synthesis.suggestion_curator import generate_suggestion_hook
                    hook_res = generate_suggestion_hook(context_text, domain_name)
                    
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
    await send_forge()

if __name__ == '__main__':
    asyncio.run(build_and_send_forge())
