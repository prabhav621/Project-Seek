import asyncio
import re
from crawl4ai import AsyncWebCrawler

async def scrape_article(url: str) -> str:
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            magic=True
        )
        if result and hasattr(result, 'markdown') and result.markdown:
            content = result.markdown
            
            # --- DEEP RESEARCH: EMBEDDED MEDIA EXTRACTION ---
            # Detect YouTube embedded videos or links inside Substack/Articles
            yt_pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)[a-zA-Z0-9_-]+'
            yt_links = list(set(re.findall(yt_pattern, content)))
            
            if yt_links:
                from src.ingestion.youtube import extract_subtitles
                content += "\n\n=== [DEEP RESEARCH: EMBEDDED VIDEO TRANSCRIPTS] ===\n"
                
                for yt_url in yt_links:
                    print(f"🕵️ Deep Research: Found embedded video -> {yt_url}")
                    try:
                        # Extract subtitles (extract_subtitles is synchronous, run in thread)
                        transcript = await asyncio.to_thread(extract_subtitles, yt_url)
                        content += f"\n--- Video: {yt_url} ---\n{transcript}\n"
                        print(f"✅ Extracted transcript for {yt_url}")
                    except Exception as e:
                        content += f"\n--- Video: {yt_url} ---\n[Failed to extract transcript: {e}]\n"
                        print(f"⚠️ Failed to extract transcript for {yt_url}: {e}")
            
            return content
        return None
