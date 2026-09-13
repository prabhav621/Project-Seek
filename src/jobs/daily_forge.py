import sys
import asyncio
from pathlib import Path
from datetime import datetime, date
from telegram import Bot

# Add src to path
src_path = Path(__file__).parent.parent
sys.path.append(str(src_path))

from db.session import SessionLocal
from intelligence.curator import curate_daily_forge
from delivery.formatter import format_daily_forge
from config import settings

async def send_forge():
    db = SessionLocal()
    try:
        target_date = date.today()
        print(f"Curating daily forge for {target_date}...")
        portfolio = curate_daily_forge(db, target_date)
        
        # Flatten portfolio into a list
        items = []
        for key, item_or_list in portfolio.items():
            if isinstance(item_or_list, list):
                items.extend(item_or_list)
            else:
                items.append(item_or_list)
                
        if not items:
            print("No items found for daily forge.")
            return

        formatted_message = format_daily_forge(items, datetime.now())
        
        bot_token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id
        
        if not bot_token or not chat_id:
            print("Telegram bot token or chat ID is missing. Cannot send message.")
            return
            
        bot = Bot(token=bot_token)
        print("Sending message via Telegram...")
        await bot.send_message(chat_id=chat_id, text=formatted_message)
        print("Done.")
        
    except Exception as e:
        print(f"Error sending forge: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(send_forge())
