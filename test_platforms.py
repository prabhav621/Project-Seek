import asyncio
import os
from src.db.session import SessionLocal
from src.ingestion.parser import UniversalLinkParser

async def test_all_platforms():
    print("🧪 TESTING UNIVERSAL INGESTION & TRANSLATION")
    print("=" * 50)
    
    urls = [
        # 1. YouTube 
        "https://www.youtube.com/watch?v=kJQP7kiw5Fk", # Despacito (Spanish - should translate!)
        # 2. Substack
        "https://substack.com/@ruiologyyy/note/p-209283301",
        # 3. Instagram Carousel
        "https://www.instagram.com/p/Ddjcz0PGmIl/?stkn=MzRlODBiNWFlZA==", 
        # 4. Web Article
        "https://paulgraham.com/greatwork.html"
    ]
    
    async with SessionLocal() as db:
        parser = UniversalLinkParser(db)
        for i, url in enumerate(urls, 1):
            print(f"\n[PLATFORM {i}] Processing: {url}")
            try:
                item = await parser.process_url(url, ingestion_mode='test')
                print(f"✅ SUCCESS! Extracted {len(item.raw_content)} characters.")
                print(f"Snippet: {item.raw_content[:200]}...")
                print(f"Assigned Domains: {item.domain_tags}")
            except Exception as e:
                print(f"❌ FAILED: {e}")

if __name__ == '__main__':
    asyncio.run(test_all_platforms())
