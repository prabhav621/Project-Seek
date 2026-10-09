import sys
import asyncio
import logging
import traceback
from pathlib import Path
from datetime import datetime, date
from telegram import Bot

logger = logging.getLogger(__name__)

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
        logger.info(f"Curating daily forge for {target_date}...")

        # Run the synchronous curator in a thread to avoid blocking
        portfolio = await asyncio.to_thread(_run_forge_sync, target_date)

        neutral_bricks = portfolio.pop('neutral_bricks', [])

        # Flatten portfolio into a list
        items = []
        for key, item_or_list in portfolio.items():
            if isinstance(item_or_list, list):
                items.extend(item_or_list)
            else:
                items.append(item_or_list)

        if not items and not neutral_bricks:
            logger.warning("No items found for daily forge.")
            return

        bot_token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id

        if not bot_token or not chat_id:
            logger.error("Telegram bot token or chat ID is missing. Cannot send message.")
            return

        bot = Bot(token=bot_token)
        logger.info("Sending message via Telegram...")
        
        if items:
            formatted_message = format_daily_forge(items, datetime.now(), [])
            
            # Telegram max length is 4096. Split safely at newlines.
            MAX_LEN = 4000
            parts = []
            remaining = formatted_message
            
            while len(remaining) > 0:
                if len(remaining) <= MAX_LEN:
                    parts.append(remaining)
                    break
                
                split_at = remaining.rfind('\n', 0, MAX_LEN)
                if split_at == -1:
                    split_at = MAX_LEN
                    
                parts.append(remaining[:split_at])
                remaining = remaining[split_at:].lstrip()

            for part in parts:
                await bot.send_message(chat_id=chat_id, text=part)
                await asyncio.sleep(0.5)
                
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        for brick in neutral_bricks:
            pointers = "\n".join([f"- {p}" for p in brick.critical_pointers]) if brick.critical_pointers else "None"
            brick_text = f"🧱 <b>Neutral Brick</b>\n\n<b>Core Thesis:</b>\n{brick.core_thesis}\n\n<b>Mechanics:</b>\n{brick.key_mechanics}\n\n<b>Pointers:</b>\n{pointers}"
            
            keyboard = [
                [
                    InlineKeyboardButton("Architect", callback_data=f"lens:architect:{brick.id}"),
                    InlineKeyboardButton("Growth", callback_data=f"lens:growth:{brick.id}")
                ],
                [
                    InlineKeyboardButton("Red Team", callback_data=f"lens:redteam:{brick.id}"),
                    InlineKeyboardButton("Validator", callback_data=f"lens:validator:{brick.id}")
                ],
                [
                    InlineKeyboardButton("First Principles", callback_data=f"lens:1stprinciple:{brick.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(chat_id=chat_id, text=brick_text, reply_markup=reply_markup, parse_mode='HTML')
            await asyncio.sleep(0.5)
            
        logger.info("Daily Forge delivery completed successfully.")

    except Exception as e:
        logger.error(f"Error sending forge: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(send_forge())

