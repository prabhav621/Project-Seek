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
    
    # Base URL extraction
    base_path = url.replace("https://x.com", "").replace("https://twitter.com", "").split("?")[0]
    
    # Try vxtwitter first, fallback to fxtwitter
    endpoints = [
        f"https://api.vxtwitter.com{base_path}",
        f"https://api.fxtwitter.com{base_path}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    data = None
    async with httpx.AsyncClient(verify=False) as client:
        for api_url in endpoints:
            try:
                response = await client.get(api_url, headers=headers, timeout=15.0)
                response.raise_for_status()
                data = response.json()
                break  # Success, exit fallback loop
            except Exception as e:
                logger.warning(f"Failed to fetch from {api_url}: {e}")
                continue
                
    if not data:
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
