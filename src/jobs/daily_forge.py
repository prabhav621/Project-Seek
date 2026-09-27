import sys
import asyncio
import traceback
from pathlib import Path
from datetime import datetime, date
from telegram import Bot

# Add project root to path
root_path = Path(__file__).resolve().parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

from src.db.session import SyncSessionLocal
from src.intelligence.curator import curate_daily_forge
from src.delivery.formatter import format_daily_forge
from src.config import settings


def _run_forge_sync(target_date: date) -> dict:
    """
    Synchronous forge logic. Runs in a thread pool so it doesn't block
    the Telegram event loop. Uses SyncSessionLocal because curator.py
    relies on synchronous SQLAlchemy ORM patterns (db.query, db.commit).
    """
    db = SyncSessionLocal()
    db.expire_on_commit = False
    try:
        portfolio = curate_daily_forge(db, target_date)
        return portfolio
    finally:
        db.close()


async def send_forge():
    try:
        target_date = date.today()
        print(f"Curating daily forge for {target_date}...")

        # Run the synchronous curator in a thread to avoid blocking
        portfolio = await asyncio.to_thread(_run_forge_sync, target_date)

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
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(send_forge())
