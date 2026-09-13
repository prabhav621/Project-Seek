import os
import sys
import time
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.ingestion.parser import UniversalLinkParser
from src.db.session import SessionLocal
from src.db.models import ContentItem

def parse_bookmarks(file_path: str, rate_limit_delay: float = 0.1):
    """
    Parses a standard Chrome/Edge bookmarks HTML file.
    Extracts URLs and pushes them as genesis ContentItems.
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    links = soup.find_all('a')
    print(f"Found {len(links)} links in bookmarks.")

    db = SessionLocal()
    added_count = 0

    try:
        for link in links:
            url = link.get('href')
            title = link.text.strip()
            
            if not url or not url.startswith('http'):
                continue

            source_type = UniversalLinkParser.get_source_type(url)
            
            # Create content item
            item = ContentItem(
                source_url=url,
                source_type=source_type.value,
                ingestion_mode='genesis',
                title=title
            )

            try:
                # Basic deduplication by URL (assuming you'd want to check this or rely on DB)
                # Note: ContentItem doesn't enforce source_url UNIQUE in DB, so we do a soft check
                exists = db.query(ContentItem.id).filter(ContentItem.source_url == url).first()
                if not exists:
                    db.add(item)
                    db.commit()
                    added_count += 1
                    print(f"Added: {url}")
            except Exception as e:
                db.rollback()
                print(f"Failed to add {url}: {e}")

            # Rate limit to avoid overwhelming the DB or downstream triggers
            time.sleep(rate_limit_delay)

    finally:
        db.close()
        
    print(f"Finished parsing bookmarks. Added {added_count} new items.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bookmarks_parser.py <path_to_bookmarks.html>")
    else:
        parse_bookmarks(sys.argv[1])
