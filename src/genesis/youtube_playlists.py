import os
import sys
import time
import yt_dlp
from sqlalchemy.exc import IntegrityError

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.ingestion.parser import UniversalLinkParser
from src.db.session import SessionLocal
from src.db.models import ContentItem

def fetch_youtube_playlist(playlist_url: str, rate_limit_delay: float = 0.5):
    """
    Uses yt-dlp to extract video URLs from a YouTube playlist and ingest them.
    """
    print(f"Fetching playlist: {playlist_url}")
    
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'skip_download': True,
    }

    db = SessionLocal()
    added_count = 0

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            
            if 'entries' not in info:
                print("No entries found or not a playlist.")
                return

            entries = info['entries']
            print(f"Found {len(entries)} videos in playlist.")

            for entry in entries:
                if not entry:
                    continue
                    
                video_url = entry.get('url')
                title = entry.get('title')
                author = entry.get('uploader')

                if not video_url:
                    continue
                
                # Make sure URL is complete
                if not video_url.startswith('http'):
                    video_url = f"https://www.youtube.com/watch?v={video_url}"

                source_type = UniversalLinkParser.get_source_type(video_url)
                
                item = ContentItem(
                    source_url=video_url,
                    source_type=source_type.value,
                    ingestion_mode='genesis',
                    title=title,
                    author=author,
                    media_type='video'
                )

                try:
                    exists = db.query(ContentItem.id).filter(ContentItem.source_url == video_url).first()
                    if not exists:
                        db.add(item)
                        db.commit()
                        added_count += 1
                        print(f"Added: {video_url} - {title}")
                except Exception as e:
                    db.rollback()
                    print(f"Failed to add {video_url}: {e}")

                # Rate limiting
                time.sleep(rate_limit_delay)

    except Exception as e:
        print(f"Error fetching playlist: {e}")
    finally:
        db.close()
        
    print(f"Finished playlist processing. Added {added_count} new videos.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python youtube_playlists.py <playlist_url>")
    else:
        fetch_youtube_playlist(sys.argv[1])
