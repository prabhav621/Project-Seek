import os
import sys
import time
import json
import re
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.ingestion.parser import UniversalLinkParser
from src.db.session import SessionLocal
from src.db.models import ContentItem

def extract_json_from_js(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts the JSON array from a Twitter/X export .js file.
    These files typically start with 'window.YTD.<name>.part0 = ['
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the first '[' character
    start_idx = content.find('[')
    if start_idx == -1:
        raise ValueError("Could not find start of JSON array in file.")
    
    json_str = content[start_idx:]
    return json.loads(json_str)

async def process_twitter_export(file_path: str, rate_limit_delay: float = 0.1):
    """
    Parses tweets.js or bookmarks.js and pushes to genesis ingestion.
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Parsing Twitter export file: {file_path}")
    
    try:
        data = extract_json_from_js(file_path)
    except Exception as e:
        print(f"Error parsing JSON from {file_path}: {e}")
        return

    added_count = 0
    async with SessionLocal() as db:
        for item in data:
            tweet_id = None
            text = None
            
            # bookmarks.js format
            if 'bookmark' in item and 'tweetId' in item['bookmark']:
                tweet_id = item['bookmark']['tweetId']
                
            # tweets.js format
            elif 'tweet' in item:
                tweet = item['tweet']
                tweet_id = tweet.get('id_str')
                text = tweet.get('full_text')
                
            if not tweet_id:
                continue
                
            # Construct standard Twitter URL
            url = f"https://x.com/i/web/status/{tweet_id}"
            source_type = UniversalLinkParser.get_source_type(url)
            
            content_item = ContentItem(
                source_url=url,
                source_type=source_type.value,
                ingestion_mode='genesis',
                raw_text=text,
                title=f"Tweet {tweet_id}" if not text else (text[:50] + "..." if len(text) > 50 else text)
            )

            try:
                exists = db.query(ContentItem.id).filter(ContentItem.source_url == url).first()
                if not exists:
                    db.add(content_item)
                    db.commit()
                    added_count += 1
                    print(f"Added: {url}")
            except Exception as e:
                db.rollback()
                print(f"Failed to add {url}: {e}")

            time.sleep(rate_limit_delay)

    print(f"Finished processing Twitter export. Added {added_count} new items.")

import asyncio

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python twitter_export.py <path_to_tweets_or_bookmarks.js>")
    else:
        asyncio.run(process_twitter_export(sys.argv[1]))
