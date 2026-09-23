import asyncio
from crawl4ai import AsyncWebCrawler

async def scrape_article(url: str) -> str:
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            magic=True
        )
        if result and hasattr(result, 'markdown') and result.markdown:
            return result.markdown
        return None
