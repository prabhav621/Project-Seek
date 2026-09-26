import asyncio
import tempfile
import os
import logging
from typing import Optional
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

async def scrape_twitter_thread(url: str) -> str:
    """
    Scrapes X/Twitter using the vxtwitter API proxy, bypassing the login wall entirely.
    Extracts embedded video audio using yt-dlp.
    """
    import httpx
    
    # 1. Convert to vxtwitter API URL
    # e.g., https://x.com/user/status/123 -> https://api.vxtwitter.com/user/status/123
    api_url = url.replace("x.com", "api.vxtwitter.com").replace("twitter.com", "api.vxtwitter.com")
    api_url = api_url.split("?")[0]  # Remove tracking params
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url, timeout=15.0)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch from vxtwitter API: {e}")
            return "Failed to extract text from Twitter."
            
    # 2. Extract perfectly clean text from the JSON
    text = data.get("text", "")
    author_name = data.get("user_name", "Unknown Author")
    author_handle = data.get("user_screen_name", "")
    
    if not text:
        return "Failed to extract meaningful text from Twitter."
        
    cleaned_thread = f"**Author:** {author_name} (@{author_handle})\n\n**Tweet Content:**\n{text}"
    
    # 3. Extract Video Audio (using yt-dlp on the original URL)
    video_transcript = await extract_twitter_video_audio(url)
    
    final_output = f"### X/Twitter Content\n\n{cleaned_thread}"
    if video_transcript:
        final_output += f"\n\n### Embedded Video Transcript\n{video_transcript}"
        
    return final_output
