import os
import re
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from src.db.session import SessionLocal
from sqlalchemy import select
from src.db.models import InterestVector, ContentItem
from src.config import settings, Tier
from src.utils.llm_client import generate_completion_async
from duckduckgo_search import DDGS
from src.ingestion.parser import UniversalLinkParser

logger = logging.getLogger(__name__)

async def is_high_signal(title: str, snippet: str) -> bool:
    """Uses FLASH/LITE tier to verify high signal-to-noise ratio."""
    prompt = (
        f"Evaluate if this resource has high intellectual density and technical substance:\n"
        f"Title: {title}\n"
        f"Snippet: {snippet}\n\n"
        f"Answer YES if it is technical, deep, or seminal. Answer NO if it is generic, superficial listicle, or marketing clickbait."
    )
    try:
        res = await generate_completion_async(
            Tier.LITE.value,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        clean = (res or "").strip().upper()
        if clean.startswith("YES"):
            return True
        if clean.startswith("NO"):
            return False
        return bool(re.search(r'\bYES\b', clean)) and not bool(re.search(r'\bNO\b', clean))
    except Exception as e:
        logger.warning(f"Signal check failed, skipping candidate to protect shadow pool: {e}")
        return False

async def run_forager():
    """
    Autonomous Forager:
    - Identifies blind spots or momentum domains from InterestVector.
    - Generates dynamic, high-signal research queries (no hardcoded gurus).
    - Filters candidate URLs through an Information Density Gate.
    - Ingests into ContentItem with ingestion_mode='auto' (Shadow Pool).
    - Zero push noise; accessible just-in-time by the Librarian.
    """
    logger.info("Initiating Autonomous Forager (Silent Audition)...")
    
    async with SessionLocal() as db:
        # Get target domains (blind spots or high momentum)
        targets = (await db.execute(select(InterestVector).filter(
            (InterestVector.is_blind_spot == True) | (InterestVector.momentum > 0.5)
        ).order_by(InterestVector.weight.desc()).limit(2))).scalars().all()
        
        if not targets:
            targets = (await db.execute(select(InterestVector).order_by(InterestVector.weight.desc()).limit(2))).scalars().all()
            
        domains = [t.domain.replace('_', ' ') for t in targets]
        if not domains:
            domains = ["technology strategy", "software engineering architecture"]
        logger.info(f"Targeting domains: {domains}")
        
        prompt = (
            f"You are a strategic research engine discovering deep technical essays, seminal papers, or authoritative post-mortems "
            f"on the following domains: {', '.join(domains)}.\n"
            f"Generate 2 highly specific, intellectual Google search queries tailored to find primary sources, niche Substacks, "
            f"or engineering blogs (e.g. site:github.blog OR site:arxiv.org OR site:substack.com).\n"
            f"Strictly avoid SEO listicles, superficial tutorials, or influencer hype.\n"
            f"Return only the 2 queries separated by newlines."
        )
        
        try:
            response = await generate_completion_async(
                Tier.FLASH.value,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            queries = [q.strip().strip('"').strip('- ') for q in (response or "").strip().split('\n') if q.strip()]
        except Exception as e:
            logger.error(f"Failed to generate forager queries: {e}")
            queries = [f"{domains[0]} architecture post-mortem", f"{domains[0]} deep dive engineering"]
        
        found_urls = []
        logger.info(f"Generated queries: {queries}")
        
        def _search_ddg(q):
            try:
                return list(DDGS(timeout=10).text(q, max_results=3, backend='html'))
            except Exception as e:
                logger.warning(f"DDG text error: {e}")
                return []

        def _search_yt(q):
            try:
                return list(DDGS(timeout=10).videos(q, max_results=2))
            except Exception as e:
                logger.warning(f"DDG video error: {e}")
                return []

        # Track A: Search for articles
        for query in queries:
            try:
                results = await asyncio.to_thread(_search_ddg, query)
                for r in results:
                    title = r.get('title', '')
                    body = r.get('body', '')
                    href = r.get('href', '')
                    if href and await is_high_signal(title, body):
                        found_urls.append((href, 'article'))
            except Exception as e:
                logger.warning(f"DDG search failed for query '{query}': {e}")
                
        # Track B: Search for YouTube video analysis
        try:
            yt_query = f"in-depth technical analysis {domains[0]}"
            yt_results = await asyncio.to_thread(_search_yt, yt_query)
            for r in yt_results:
                content_url = r.get('content', '')
                if 'youtube.com' in content_url:
                    found_urls.append((content_url, 'youtube'))
        except Exception as e:
            logger.warning(f"DDG video search failed: {e}")
                
        logger.info(f"Found {len(found_urls)} high-signal candidates to forage.")

    # Limit to top 2 items per run to respect daily ingestion pacing
    to_process = found_urls[:2]
    semaphore = asyncio.Semaphore(2)

    async def process_candidate(url, hint):
        async with semaphore:
            logger.info(f"Auditioning candidate: {url}")
            async with SessionLocal() as local_db:
                parser = UniversalLinkParser(db_session=local_db)
                try:
                    await parser.process_url(url, ingestion_mode='auto')
                    logger.info(f"Successfully ingested shadow item: {url}")
                except Exception as e:
                    logger.error(f"Failed to ingest candidate {url}: {e}")

    tasks = [asyncio.create_task(process_candidate(url, hint)) for url, hint in to_process]
    if tasks:
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(run_forager())
