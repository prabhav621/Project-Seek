import asyncio
from crawl4ai import AsyncWebCrawler

async def scrape_article(url: str) -> str:
    """
    Scrapes generic articles and Substack posts and extracts clean Markdown using crawl4ai.
    """
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        return result.markdown
