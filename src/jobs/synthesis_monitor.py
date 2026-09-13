import sys
import asyncio
from pathlib import Path
from telegram import Bot

# Add src to path
src_path = Path(__file__).parent.parent
sys.path.append(str(src_path))

from db.session import SessionLocal
from db.models import ContentItem
from src.config import settings

async def check_failures():
    db = SessionLocal()
    try:
        failed_items = db.query(ContentItem).filter(ContentItem.extraction_status == 'failed').all()
        if not failed_items:
            print("No failed items found.")
            return
            
        bot_token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id
        
        if not bot_token or not chat_id:
            print("Telegram bot token or chat ID is missing. Cannot send message.")
            return
            
        bot = Bot(token=bot_token)
        
        # Prepare message
        msg = f"⚠️ *Synthesis Monitor Alert*\n\nFound {len(failed_items)} failed content item(s):\n"
        for item in failed_items[:5]:  # limit to 5
            msg += f"- ID: {item.id}\n  Source: {item.source_type}\n  URL: {item.source_url}\n"
            
        if len(failed_items) > 5:
            msg += f"...and {len(failed_items) - 5} more."
            
        print("Sending alert via Telegram...")
        await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        print("Alert sent.")
        
    except Exception as e:
        print(f"Error checking failures: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(check_failures())
