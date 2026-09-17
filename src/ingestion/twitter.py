import asyncio
import tempfile
import os
import logging
from typing import Optional
from crawl4ai import AsyncWebCrawler
from google import genai
from src.config import settings

logger = logging.getLogger(__name__)

async def extract_twitter_video_audio(url: str) -> Optional[str]:
    """Attempts to extract and transcribe embedded video audio from a tweet using yt-dlp."""
    try:
        import yt_dlp
        from src.ingestion.media import transcribe_media
    except ImportError:
        logger.error("Missing yt_dlp or media module for Twitter video extraction.")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        out_tmpl = os.path.join(tmpdir, 'tweet_audio.%(ext)s')
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_tmpl,
            'quiet': True,
            'no_warnings': True,
            'extract_audio': True,
            'audio_format': 'm4a',
        }
        
        try:
            def run_ydl():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            
            await asyncio.to_thread(run_ydl)
            
            files = os.listdir(tmpdir)
            if not files:
                return None
                
            audio_path = os.path.join(tmpdir, files[0])
            transcript = await asyncio.to_thread(transcribe_media, audio_path)
            return transcript
            
        except Exception as e:
            logger.debug(f"No video found or extraction failed for {url}: {e}")
            return None

async def clean_twitter_markdown(raw_markdown: str) -> str:
    """Uses Gemini Flash to strip unrelated UI elements and random replies from the raw thread."""
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = """
    Below is a raw markdown scrape of a Twitter/X thread. It contains UI elements, sidebars, and often unrelated replies from other users.
    Please extract ONLY the original author's thread/content. Stitch the thread together into clean, readable markdown.
    Do not add extra commentary. If there is no coherent text, just return the raw text as best you can.
    
    RAW SCRAPE:
    """
    
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-3.6-flash',
            contents=[prompt + "\n" + raw_markdown]
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Failed to clean Twitter markdown with Gemini: {e}")
        return raw_markdown

async def scrape_twitter_thread(url: str) -> str:
    """
    Scrapes X/Twitter threads using Crawl4AI (with JS scrolling), cleans the output with Gemini,
    and extracts any embedded video audio using yt-dlp.
    """
    js_code = """
    async () => {
        for(let i = 0; i < 4; i++) {
            window.scrollBy(0, window.innerHeight * 1.5);
            await new Promise(r => setTimeout(r, 1500));
        }
    }
    """
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=url,
            js_code=js_code,
            wait_for="article"
        )
        raw_markdown = result.markdown
        
    if not raw_markdown:
        return "Failed to extract text from Twitter."
        
    cleaned_thread = await clean_twitter_markdown(raw_markdown)
    video_transcript = await extract_twitter_video_audio(url)
    
    final_output = f"### Twitter Thread Extracted Content\n\n{cleaned_thread}"
    if video_transcript:
        final_output += f"\n\n### Embedded Video Transcript\n{video_transcript}"
        
    return final_output
