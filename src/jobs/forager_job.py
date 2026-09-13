import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from src.db.session import SessionLocal
from src.db.models import InterestVector, ContentItem
from src.ingestion.embedder import get_embedder
from src.synthesis.domain_tagger import DomainTagger
from src.config import settings
from google import genai
from duckduckgo_search import DDGS
from src.ingestion.parser import UniversalLinkParser

async def run_forager():
    print("Initiating Autonomous Forager...")
    client = genai.Client(api_key=settings.gemini_api_key)
    
    with SessionLocal() as db:
        # Get target domains (blind spots or high momentum)
        targets = db.query(InterestVector).filter(
            (InterestVector.is_blind_spot == True) | (InterestVector.momentum > 0.5)
        ).order_by(InterestVector.weight.desc()).limit(2).all()
        
        if not targets:
            targets = db.query(InterestVector).order_by(InterestVector.weight.desc()).limit(2).all()
            
        domains = [t.domain.replace('_', ' ') for t in targets]
        print(f"Targeting domains: {domains}")
        
        # Ask Gemini to generate search queries
        prompt = f"Generate 2 highly specific, intellectual Google search queries to find insightful articles or essays about: {', '.join(domains)}. Return just the 2 queries separated by newlines."
        response = client.models.generate_content(
            model=settings.flash_model,
            contents=prompt
        )
        
        queries = [q.strip().strip('"').strip('- ') for q in response.text.strip().split('\n') if q.strip()]
        
        found_urls = []
        ddgs = DDGS()
        
        print(f"Generated queries: {queries}")
        
        # Track A: Search for articles
        for query in queries:
            results = ddgs.text(query, max_results=2)
            for r in results:
                found_urls.append((r['href'], 'article'))
                
        # Track B: Search for YouTube video
        yt_query = f"in-depth analysis {domains[0]}"
        yt_results = ddgs.videos(yt_query, max_results=1)
        for r in yt_results:
            if 'youtube.com' in r.get('content', ''):
                found_urls.append((r['content'], 'youtube'))
                
        print(f"Found {len(found_urls)} URLs to forage.")
        
        # Pass them into the UniversalLinkParser
        parser = UniversalLinkParser(db_session=db)
        for url, hint in found_urls:
            print(f"Foraging: {url}")
            try:
                await parser.process_url(url, ingestion_mode='auto')
                print(f"Successfully ingested {url}")
            except Exception as e:
                print(f"Failed to ingest {url}: {e}")

if __name__ == '__main__':
    asyncio.run(run_forager())
