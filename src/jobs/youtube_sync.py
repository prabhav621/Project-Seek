import os
import sys
import argparse
import tempfile
import logging
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from sqlalchemy import select

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# Load .env explicitly if needed
load_dotenv(project_root / ".env")

import yt_dlp
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from src.db.session import SessionLocal
from src.db.models import ContentItem
from src.ingestion.parser import UniversalLinkParser
from src.ingestion.media import transcribe_media
from src.ingestion.embedder import get_default_embedder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
CLIENT_SECRETS_FILE = os.environ.get("YOUTUBE_CLIENT_SECRETS", os.path.join(project_root, "client_secret.json"))
TOKEN_FILE = os.path.join(project_root, "token.json")

def get_youtube_client():
    creds = None
    if os.path.exists(TOKEN_FILE):
        logger.info("Loading credentials from token.json")
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials")
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                raise FileNotFoundError(f"Missing {CLIENT_SECRETS_FILE}. Please provide a client_secret.json for YouTube Data API.")
            
            logger.info("Starting OAuth2 flow to authenticate")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('youtube', 'v3', credentials=creds)


def download_audio(url: str, output_dir: str) -> str:
    """Download the audio of a YouTube video using yt-dlp."""
    logger.info(f"Downloading audio for {url}...")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = os.path.join(output_dir, f"{info['id']}.mp3")
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Failed to download audio for {url}")
        return filename

async def process_video(item: dict, db) -> bool:
    """
    Process a single video item from the liked playlist.
    Returns True if the item was processed (or attempted), False if it was already in the DB (skipped).
    """
    video_id = item["contentDetails"]["videoId"]
    title = item.get("snippet", {}).get("title", f"Unknown Title ({video_id})")
    author = item.get("snippet", {}).get("videoOwnerChannelTitle", "Unknown Channel")
    source_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Check if already processed
    existing = (await db.execute(select(ContentItem).filter(ContentItem.source_url == source_url))).scalars().first()
    if existing:
        logger.info(f"Skipping already ingested video: {title} ({source_url})")
        return False
        
    logger.info(f"Ingesting new video: {title} ({source_url})")
    
    source_type = UniversalLinkParser.get_source_type(source_url)
    
    content_item = ContentItem(
        source_url=source_url,
        source_type=source_type.value,
        title=title,
        author=author,
        ingestion_mode="auto",
        media_type="video",
        extraction_status="processing",
        processed=False
    )
    
    db.add(content_item)
    await db.commit()
    await db.refresh(content_item)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = download_audio(source_url, tmpdir)
            
            logger.info("Transcribing audio...")
            transcript = transcribe_media(audio_path)
            
            if not transcript:
                raise ValueError("Transcription returned empty or failed.")
            
            content_item.raw_text = transcript
            content_item.transcript_source = "gemini_audio"
            
            logger.info("Generating embeddings for the transcript...")
            embedder = get_default_embedder()
            vector = embedder.embed_text(transcript)
            content_item.embedding = vector
            
            content_item.extraction_status = "completed"
            content_item.processed = True
            
            await db.commit()
            logger.info(f"Successfully processed and embedded: {title}")
            
    except Exception as e:
        logger.error(f"Failed to process video {video_id}: {e}")
        await db.rollback()
        # Mark as failed in DB
        failed_item = (await db.execute(select(ContentItem).filter(ContentItem.id == content_item.id))).scalars().first()
        if failed_item:
            failed_item.extraction_status = "failed"
            await db.commit()
            
    return True

async def sync_liked_videos(scan_all=False):
    youtube = get_youtube_client()
    async with SessionLocal() as db:
        try:
            logger.info("Fetching 'Liked Videos' playlist...")
            request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId="LL",
                maxResults=50
            )
            
            while request is not None:
                response = request.execute()
                items = response.get("items", [])
                
                if not items:
                    logger.info("No items found in playlist.")
                    break
                    
                for item in items:
                    was_processed = await process_video(item, db)
                    if not was_processed and not scan_all:
                        logger.info("Found an already processed video. Assuming all older videos are processed. Stopping sync.")
                        return
                
                # Fetch next page
                request = youtube.playlistItems().list_next(request, response)
                
        except Exception as e:
            logger.error(f"An error occurred during sync: {e}")
        finally:
            logger.info("Sync job finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync YouTube Liked Videos to Ingestion Pipeline")
    parser.add_argument("--all", action="store_true", help="Scan the entire playlist instead of stopping at the first existing video")
    args = parser.parse_args()
    
    asyncio.run(sync_liked_videos(scan_all=args.all))
