import asyncio
from crawl4ai import AsyncWebCrawler

async def scrape_twitter_thread(url: str) -> str:
    """
    Scrapes and unrolls X/Twitter threads into continuous markdown text using crawl4ai.
    """
    async with AsyncWebCrawler() as crawler:
        # Wait for the tweet article containers to load in the DOM
        result = await crawler.arun(
            url=url,
            wait_for="article"
        )
        return result.markdown
