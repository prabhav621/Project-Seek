from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import sys
import asyncio
import logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
import traceback
from pathlib import Path
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import MessageEntityType, ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters, MessageReactionHandler, CommandHandler, CallbackQueryHandler
from datetime import datetime, timedelta

active_focus = {}

# Add project root to path
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from src.config import settings
from src.db.session import SessionLocal, SyncSessionLocal
from sqlalchemy import select
from src.db.models import DailyItem, InterestVector
from src.intelligence.reply_analyzer import ReplyAnalyzer
from src.intelligence.drift_engine import update_drift
from src.models import DailyItemResponse

# Global ingestion queue to serialize all playlist/batch work
_ingestion_queue = asyncio.Queue()
_worker_running = False


async def _ingestion_worker(bot):
    """Single background worker that processes ingestion jobs sequentially.
    This prevents multiple playlists from competing for API rate limits."""
    global _worker_running
    _worker_running = True
    while True:
        job = await _ingestion_queue.get()
        try:
            job_type = job.get("type")
            chat_id = job.get("chat_id")
            if job_type == "playlist":
                await _process_playlist(job["url"], chat_id, bot)
            elif job_type == "individual":
                await _process_individual(job["urls"], chat_id, bot)
        except Exception as e:
            print(f"Ingestion worker error: {e}")
            traceback.print_exc()
            try:
                await bot.send_message(chat_id=job.get("chat_id"), text=f"âš ï¸ Ingestion job failed: {str(e)[:200]}")
            except Exception:
                pass
        finally:
            _ingestion_queue.task_done()


async def _process_individual(urls: list, chat_id: int, bot):
    from src.ingestion.parser import UniversalLinkParser

    success_count = 0
    fail_count = 0

    for url in urls:
        # Fresh DB session per URL to prevent connection timeout
        try:
            async with SessionLocal() as db:
                parser = UniversalLinkParser(db)
                await parser.process_url(url, ingestion_mode='manual')
                success_count += 1
                print(f"Ingested: {url}")
        except Exception as e:
            fail_count += 1
            print(f"Failed: {url} - {e}")

        await asyncio.sleep(12)

    try:
        await bot.send_message(chat_id=chat_id, text=f"✅ Batch ingestion completed!\nSuccess: {success_count}\nFailed: {fail_count}")
    except Exception:
        print(f"Batch done: {success_count} success, {fail_count} failed (couldn't notify Telegram)")


async def _process_playlist(playlist_url: str, chat_id: int, bot):
    import yt_dlp

    # Step 1: Extract video URLs from playlist (no API calls needed)
    def extract_playlist():
        ydl_opts = {'extract_flat': True, 'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(playlist_url, download=False)

    video_urls = []
    try:
        info = await asyncio.to_thread(extract_playlist)
        if 'entries' in info:
            for entry in info['entries']:
                if entry and entry.get('url'):
                    v_url = entry.get('url')
                    if not v_url.startswith('http'):
                        v_url = f"https://www.youtube.com/watch?v={v_url}"
                    video_urls.append(v_url)
    except Exception as e:
        print(f"Failed to extract playlist: {e}")
        try:
            await bot.send_message(chat_id=chat_id, text=f"âŒ Failed to extract playlist {playlist_url}: {str(e)[:200]}")
        except Exception:
            pass
        return

    total = len(video_urls)
    print(f"Found {total} videos in playlist. Ingesting...")
    try:
        await bot.send_message(chat_id=chat_id, text=f"Found {total} videos in playlist. Starting ingestion with adaptive rate limiting...")
    except Exception:
        pass

    # Step 2: Process each video with a FRESH db session per video
    # Uses adaptive rate limiting to avoid YouTube IP bans
    from src.ingestion.parser import UniversalLinkParser
    import random

    failed_urls = []
    success_count = 0
    fail_count = 0
    consecutive_errors = 0

    MICRO_BATCH_SIZE = 10
    MICRO_BATCH_PAUSE = 120  # 2 minutes between micro-batches

    for i, v_url in enumerate(video_urls):
        is_youtube = "youtube.com" in v_url or "youtu.be" in v_url

        try:
            async with SessionLocal() as db:
                parser = UniversalLinkParser(db)
                await parser.process_url(v_url, ingestion_mode='manual')
                success_count += 1
                print(f"[{i+1}/{total}] ✅ Ingested: {v_url}")
        except Exception as e:
            fail_count += 1
            failed_urls.append(v_url)
            print(f"[{i+1}/{total}] ❌ Error on {v_url}: {e}")

        # â”€â”€â”€ Pacing (Gemini RPM Calibration) â”€â”€â”€â”€â”€â”€
        if is_youtube:
            # Gemini Free Tier limit is 15 RPM. 
            # We make TWO calls per video (Embedder + Domain Tagger).
            # 15 RPM / 2 calls = 7.5 videos per min. 60s / 7.5 = 8.0s min delay.
            # 9.0s guarantees we stay safely under the limit.
            delay = 12
        else:
            delay = 12

        await asyncio.sleep(delay)

    # â”€â”€â”€ Log Failures â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if failed_urls:
        try:
            with open("failed_ingestions.txt", "a") as f:
                for u in failed_urls:
                    f.write(f"{u}\n")
        except Exception as e:
            print(f"Could not write to failed_ingestions.txt: {e}")

    try:
        final_msg = f"✅ Playlist ingestion completed!\nSuccess: {success_count}\nFailed: {fail_count}\nTotal: {total}"
        if failed_urls:
            final_msg += f"\n\nâš ï¸ {len(failed_urls)} URLs failed. They have been logged to 'failed_ingestions.txt' on the server."
        await bot.send_message(chat_id=chat_id, text=final_msg)
    except Exception:
        print(f"Playlist done: {success_count} success, {fail_count} failed (couldn't notify Telegram)")


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Message handler that intercepts any URLs forwarded to the bot,
    prints the URL to stdout, and responds with an acknowledgment.
    """
    message = update.message
    if not message:
        return

    urls = []

    # Extract URLs from message text
    if message.text:
        entities = message.parse_entities([MessageEntityType.URL, MessageEntityType.TEXT_LINK])
        for entity, text in entities.items():
            if entity.type == MessageEntityType.URL:
                urls.append(text)
            elif entity.type == MessageEntityType.TEXT_LINK:
                urls.append(entity.url)

    # Extract URLs from message caption (e.g. if forwarded with an image)
    if message.caption:
        caption_entities = message.parse_caption_entities([MessageEntityType.URL, MessageEntityType.TEXT_LINK])
        for entity, text in caption_entities.items():
            if entity.type == MessageEntityType.URL:
                urls.append(text)
            elif entity.type == MessageEntityType.TEXT_LINK:
                urls.append(entity.url)

    if urls:
        # Separate playlists from individual URLs
        playlists = [u for u in urls if "youtube.com" in u and "list=" in u]
        individual = [u for u in urls if u not in playlists]

        queue_size = _ingestion_queue.qsize()
        status = f" ({queue_size} jobs already queued)" if queue_size > 0 else ""

        await message.reply_text(
            f"Intercepted {len(playlists)} playlists and {len(individual)} individual links.\n"
            f"Queuing for sequential background ingestion{status}..."
        )

        # Ensure the worker is running
        global _worker_running
        if not _worker_running:
            asyncio.create_task(_ingestion_worker(context.bot))

        # Queue jobs instead of spawning competing tasks
        for p in playlists:
            await _ingestion_queue.put({"type": "playlist", "url": p, "chat_id": message.chat_id})

        if individual:
            await _ingestion_queue.put({"type": "individual", "urls": individual, "chat_id": message.chat_id})


async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reaction = update.message_reaction
    if not reaction:
        return

    async with SessionLocal() as db:
        latest_item = (await db.execute(select(DailyItem).order_by(DailyItem.created_at.desc()))).scalars().first()
        if latest_item:
            items = (await db.execute(select(DailyItem).filter(DailyItem.forge_date == latest_item.forge_date))).scalars().all()
            for item in items:
                if item.engagement == 'pending':
                    item.engagement = 'read'
                    # update_drift uses sync ORM — run in thread with its own sync session
                    await asyncio.to_thread(_update_drift_sync, str(item.id), 'read')
            await db.commit()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    chat_id = message.chat_id
    focus = None
    if chat_id in active_focus:
        focus_data = active_focus[chat_id]
        from datetime import datetime
        if datetime.now() > focus_data['expires_at']:
            del active_focus[chat_id]
        else:
            focus = focus_data['goal']

    from src.synthesis.strategy_generator import DualLayerContextEngine
    engine = DualLayerContextEngine()

    # 1. CONTEXTUAL BRICK / BOT MESSAGE SPARRING (User replied to a message from the bot)
    if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
        original_text = message.reply_to_message.text or ""
        user_query = message.text

        # Detect if replying to a Kata or Daily Forge
        is_kata = any(k in original_text.upper() for k in ["QUICK KATA", "KATA #", "FORGE", "KATA SPARRING"])
        
        if is_kata:
            processing_msg = await message.reply_text("🥋 Sparring on your Kata...")
            try:
                async with SessionLocal() as db:
                    insight = await engine.spar_kata(original_text, user_query, db, focus)
                output = f"🥋 **Kata Sparring:**\n\n{insight}"
                if focus:
                    output = f"[❗️ Focus State: {focus}]\n\n" + output
                await processing_msg.edit_text(output, parse_mode='Markdown')
            except Exception as e:
                await processing_msg.edit_text(f"Could not process Kata reply: {e}")
            return

        processing_msg = await message.reply_text("🤔 Thinking with you...")
        try:
            insight = await engine.ask_brick(original_text, user_query, focus)
            output = f"🧠 **Insight:**\n\n{insight}"
            if focus:
                output = f"[❗️ Focus State: {focus}]\n\n" + output
            await processing_msg.edit_text(output, parse_mode='Markdown')
        except Exception as e:
            await processing_msg.edit_text(f"Could not process reply: {e}")
        return

    # 2. RAW MESSAGE -> REVERSE RAG / LIBRARIAN
    query = message.text
    processing_msg = await message.reply_text("📚 Searching your knowledge base...")

    try:
        async with SessionLocal() as db:
            insight = await engine.run_librarian(query, db, focus)

        output = f"📚 **The Librarian Says:**\n\n{insight}"
        if focus:
            output = f"[❗️ Focus State: {focus}]\n\n" + output

        await processing_msg.edit_text(output, parse_mode='Markdown')
    except Exception as e:
        await processing_msg.edit_text(f"Librarian search failed: {e}")



def _update_drift_sync(item_id: str, engagement_type: str, reply_analysis: dict = None):
    """Thread-safe wrapper for update_drift. Creates its own sync session."""
    db = SyncSessionLocal()
    try:
        update_drift(db, item_id, engagement_type, reply_analysis)
    finally:
        db.close()


async def handle_forge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔨 Forging your daily digest... This might take 30-60 seconds.")
    from src.jobs.forge_builder import build_and_send_forge
    asyncio.create_task(build_and_send_forge())


async def post_init(application: Application):
    """Start the ingestion worker when the bot starts."""
    global _worker_running
    if not _worker_running:
        asyncio.create_task(_ingestion_worker(application.bot))

    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Kolkata'))

    async def scheduled_forge():
        from src.jobs.forge_builder import build_and_send_forge
        await build_and_send_forge()

    scheduler.add_job(scheduled_forge, 'cron', hour=8, minute=0)
    scheduler.start()
    print("⏰ Daily Forge Scheduler started for 8:00 AM IST")
    
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("forge", "Generate the Daily Forge"),
        BotCommand("help", "Show help message"),
        BotCommand("strategize", "Ingest URL to Neutral Brick"),
        BotCommand("focus", "Set temporary focus"),
        BotCommand("unfocus", "Clear focus"),
        BotCommand("lens", "Apply a lens to a replied brick"),
        BotCommand("lens_architect", "Apply architect lens"),
        BotCommand("lens_growth", "Apply growth lens"),
        BotCommand("lens_redteam", "Apply redteam lens"),
        BotCommand("lens_validator", "Apply validator lens"),
        BotCommand("lens_first_principles", "Apply first_principles lens"),
    ]
    await application.bot.set_my_commands(commands)




async def handle_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💡 Seek is now continuously contextual!\n\n"
        "• Reply to any Neutral Brick to interrogate or spar with it.\n"
        "• Send any raw thought or question to query your Librarian.\n"
        "There are no rigid chat sessions to end."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Message handler that intercepts documents (PDF, Markdown, TXT),
    downloads them, and extracts their text natively via Gemini.
    """
    document = update.message.document
    if not document:
        return
        
    file_id = document.file_id
    file_name = document.file_name or f"document_{file_id}"
    mime_type = document.mime_type
    
    await update.message.reply_text(f"📥 Received document: {file_name}. Downloading and extracting text via Gemini...")
    
    try:
        telegram_file = await context.bot.get_file(file_id)
        
        import tempfile
        import os
        from src.ingestion.parser import UniversalLinkParser
        from src.db.session import SessionLocal
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, file_name)
            await telegram_file.download_to_drive(file_path)
            
            async with SessionLocal() as db:
                parser = UniversalLinkParser(db)
                await parser.process_document(file_path, file_name, mime_type)
                
        await update.message.reply_text(f"✅ Successfully ingested and embedded document: {file_name}")
    except Exception as e:
        logger.error(f"Failed to process document {file_name}: {e}")
        await update.message.reply_text(f"❌ Failed to ingest document {file_name}:\n{str(e)[:200]}")

async def handle_focus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message: return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Please provide a goal. Usage: /focus [goal]")
        return
        
    goal = parts[1]
    if goal.lower() == "clear":
        chat_id = message.chat_id
        if chat_id in active_focus:
            del active_focus[chat_id]
        await message.reply_text("🌐 **Focus cleared.** Returning to primary mission directive.", parse_mode=ParseMode.MARKDOWN)
        return

    chat_id = message.chat_id
    active_focus[chat_id] = {
        "goal": goal,
        "expires_at": datetime.now() + timedelta(minutes=15)
    }
    await message.reply_text(f"🎯 **Focus locked:** {goal}. I am now prioritizing this above my general mission. Type `/unfocus` to reset.", parse_mode=ParseMode.MARKDOWN)

async def handle_unfocus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message: return
    
    chat_id = message.chat_id
    if chat_id in active_focus:
        del active_focus[chat_id]
        
    await message.reply_text("🌐 **Focus cleared.** Returning to primary mission directive.", parse_mode=ParseMode.MARKDOWN)

async def handle_strategize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message: return
    
    args = context.args
    if not args:
        await message.reply_text("Because of Telegram's dropdown rules, tapping a menu command sends it immediately. Please explicitly type: /strategize <URL>")
        return
        
    url = args[0]
        
    chat_id = message.chat_id
    focus = None
    
    if chat_id in active_focus:
        focus_data = active_focus[chat_id]
        if datetime.now() > focus_data["expires_at"]:
            del active_focus[chat_id]
        else:
            focus = focus_data["goal"]
            
    processing_msg = await message.reply_text("Extraction started. Ingesting content...")
    
    try:
        from src.ingestion.parser import UniversalLinkParser
        async with SessionLocal() as db:
            parser = UniversalLinkParser(db)
            content_item = await parser.process_url(url, ingestion_mode='manual')
            
            if not content_item or not content_item.raw_text:
                await processing_msg.edit_text("Failed to extract meaningful text from this URL.")
                return
                
            await processing_msg.edit_text("Content ingested. Generating Neutral Brick...")
            
            from src.synthesis.strategy_generator import DualLayerContextEngine
            engine = DualLayerContextEngine()
            
            brick_dict = await engine.generate_strategy(content_item.raw_text[:8000], focus)
            
            if not brick_dict:
                await processing_msg.edit_text("Failed to generate strategy brick from content.")
                return
                
            from src.db.models import NeutralBrick
            # Check if brick exists
            existing_brick = (await db.execute(select(NeutralBrick).filter(NeutralBrick.source_content_id == content_item.id))).scalar_one_or_none()
            
            if not existing_brick:
                new_brick = NeutralBrick(
                    source_content_id=content_item.id,
                    core_thesis=brick_dict.get('core_thesis', 'N/A'),
                    key_mechanics=brick_dict.get('key_mechanics', 'N/A'),
                    critical_pointers=brick_dict.get('critical_pointers', [])
                )
                db.add(new_brick)
                await db.commit()
                
            # Format output
            pointers = "\n".join(f"• {p}" for p in brick_dict.get('critical_pointers', []))
            output = (
                f"🧱 **Core Thesis:**\n{brick_dict.get('core_thesis', '')}\n\n"
                f"⚙️ **Key Mechanics:**\n{brick_dict.get('key_mechanics', '')}\n\n"
                f"🎯 **Critical Pointers:**\n{pointers}"
            )
            
            if focus:
                output = f"[❗️ Focus State: {focus}]\n\n" + output
                
            await processing_msg.edit_text(output, parse_mode='Markdown')
            
    except Exception as e:
        await processing_msg.edit_text(f"Error during strategize: {e}")

async def handle_lens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message: return
    
    # 1. Determine target Brick text
    brick_text = ""
    brick_id = None
    
    if message.reply_to_message and message.reply_to_message.text:
        brick_text = message.reply_to_message.text
    else:
        # Fallback to the latest Neutral Brick in DB
        async with SessionLocal() as db:
            from src.db.models import NeutralBrick
            latest_brick = (await db.execute(select(NeutralBrick).order_by(NeutralBrick.created_at.desc()))).scalars().first()
            if latest_brick:
                brick_id = str(latest_brick.id)
                pointers = "\n".join([f"- {p}" for p in latest_brick.critical_pointers]) if latest_brick.critical_pointers else "None"
                brick_text = f"🧱 Neutral Brick\n\nCore Thesis:\n{latest_brick.core_thesis}\n\nMechanics:\n{latest_brick.key_mechanics}\n\nPointers:\n{pointers}"
    
    if not brick_text:
        await message.reply_text("No Neutral Brick found. Ingest an article or run /forge first!")
        return

    text = message.text or ""
    command = text.split()[0].lower() if text else ""
    
    chat_id = message.chat_id
    focus = None
    if chat_id in active_focus:
        focus_data = active_focus[chat_id]
        if datetime.now() > focus_data["expires_at"]:
            del active_focus[chat_id]
        else:
            focus = focus_data["goal"]

    from src.synthesis.strategy_generator import DualLayerContextEngine
    engine = DualLayerContextEngine()

    # 2. Check for explicit shortcut command like /lens_architect
    if command.startswith("/lens_"):
        lens_name = command.replace("/lens_", "")
        processing_msg = await message.reply_text(f"🔍 Applying {lens_name.replace('_', ' ').title()} Lens...")
        res = await engine.apply_lens(brick_text, lens_name, focus)
        await processing_msg.edit_text(res or "Failed to apply lens.")
        return

    # 3. Check arguments for /lens
    args = context.args or []
    
    # If bare /lens with no arguments -> Render Inline Keyboard Picker!
    if not args:
        context.chat_data["pending_lens_brick_text"] = brick_text
        keyboard = [
            [
                InlineKeyboardButton("🏗️ Architect", callback_data="lens_choice:architect"),
                InlineKeyboardButton("📈 Growth", callback_data="lens_choice:growth")
            ],
            [
                InlineKeyboardButton("🛡️ Red Team", callback_data="lens_choice:red_team"),
                InlineKeyboardButton("✅ Validator", callback_data="lens_choice:validator")
            ],
            [
                InlineKeyboardButton("⚛️ First Principles", callback_data="lens_choice:first_principles")
            ]
        ]
        await message.reply_text(
            "🔍 **Select an analytical lens to apply:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    # 4. If /lens has arguments (e.g. /lens growth OR /lens unit economics)
    target_arg = " ".join(args).strip().lower()
    canonical_lenses = {
        "architect": "architect",
        "growth": "growth",
        "redteam": "red_team",
        "red_team": "red_team",
        "validator": "validator",
        "first_principles": "first_principles",
        "firstprinciples": "first_principles",
        "1stprinciple": "first_principles"
    }

    if target_arg in canonical_lenses:
        lens_name = canonical_lenses[target_arg]
        processing_msg = await message.reply_text(f"🔍 Applying {lens_name.replace('_', ' ').title()} Lens...")
        res = await engine.apply_lens(brick_text, lens_name, focus)
        await processing_msg.edit_text(res or "Failed to apply lens.")
    else:
        # Ad-hoc custom lens: treat as contextual sparring via ask_brick!
        processing_msg = await message.reply_text(f"🧠 Examining Brick through lens of: '{target_arg}'...")
        prompt = f"Analyze this Brick through the strategic lens of: {target_arg}"
        res = await engine.ask_brick(brick_text, prompt, focus)
        await processing_msg.edit_text(res or "Failed to analyze.")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id
    focus = None
    if chat_id in active_focus:
        focus_data = active_focus[chat_id]
        if datetime.now() > focus_data["expires_at"]:
            del active_focus[chat_id]
        else:
            focus = focus_data["goal"]

    from src.synthesis.strategy_generator import DualLayerContextEngine
    engine = DualLayerContextEngine()

    # Case A: From /lens inline picker (lens_choice:<lens_name>)
    if data.startswith("lens_choice:"):
        lens_name = data.split(":", 1)[1]
        brick_text = context.chat_data.get("pending_lens_brick_text")
        
        if not brick_text:
            async with SessionLocal() as db:
                from src.db.models import NeutralBrick
                latest_brick = (await db.execute(select(NeutralBrick).order_by(NeutralBrick.created_at.desc()))).scalars().first()
                if latest_brick:
                    pointers = "\n".join([f"- {p}" for p in latest_brick.critical_pointers]) if latest_brick.critical_pointers else "None"
                    brick_text = f"🧱 Neutral Brick\n\nCore Thesis:\n{latest_brick.core_thesis}\n\nMechanics:\n{latest_brick.key_mechanics}\n\nPointers:\n{pointers}"

        if not brick_text:
            await query.edit_message_text("No Brick found to apply lens to.")
            return

        await query.edit_message_text(f"🔍 Applying {lens_name.replace('_', ' ').title()} Lens...")
        response = await engine.apply_lens(brick_text, lens_name, focus)
        await context.bot.send_message(chat_id=chat_id, text=response or "Failed to apply lens.")
        return

    # Case B: From Daily Forge inline buttons (lens:<lens_name>:<brick_id>)
    if data.startswith("lens:"):
        parts = data.split(":")
        if len(parts) == 3:
            _, lens_name, brick_id = parts
            
            async with SessionLocal() as db:
                from src.db.models import NeutralBrick
                import uuid
                try:
                    b_id = uuid.UUID(brick_id)
                except ValueError:
                    await context.bot.send_message(chat_id=chat_id, text="Invalid Brick ID.")
                    return
                brick = (await db.execute(select(NeutralBrick).filter(NeutralBrick.id == b_id))).scalars().first()
                
            if not brick:
                await context.bot.send_message(chat_id=chat_id, text="Brick not found.")
                return

            pointers = "\n".join([f"- {p}" for p in brick.critical_pointers]) if brick.critical_pointers else "None"
            brick_text = f"🧱 Neutral Brick\n\nCore Thesis:\n{brick.core_thesis}\n\nMechanics:\n{brick.key_mechanics}\n\nPointers:\n{pointers}"
            
            response = await engine.apply_lens(brick_text, lens_name, focus)
            if response:
                await context.bot.send_message(chat_id=chat_id, text=response)
            else:
                await context.bot.send_message(chat_id=chat_id, text="Failed to apply lens.")

def main():
    token = settings.telegram_bot_token
    if not token:
        print("Error: telegram_bot_token is missing from configuration.")
        return

    application = Application.builder().token(token).build()

    url_filter = (
        filters.Entity(MessageEntityType.URL) |
        filters.Entity(MessageEntityType.TEXT_LINK) |
        filters.CaptionEntity(MessageEntityType.URL) |
        filters.CaptionEntity(MessageEntityType.TEXT_LINK)
    )

    application.add_handler(CommandHandler("forge", handle_forge))
    application.add_handler(CommandHandler("end", handle_end))
    application.add_handler(CommandHandler("focus", handle_focus))
    application.add_handler(CommandHandler("unfocus", handle_unfocus))
    application.add_handler(CommandHandler("strategize", handle_strategize))
    
    application.add_handler(CommandHandler("lens", handle_lens))
    application.add_handler(CommandHandler("lens_architect", handle_lens))
    application.add_handler(CommandHandler("lens_growth", handle_lens))
    application.add_handler(CommandHandler("lens_redteam", handle_lens))
    application.add_handler(CommandHandler("lens_validator", handle_lens))
    application.add_handler(CommandHandler("lens_first_principles", handle_lens))
    
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    application.add_handler(MessageHandler(url_filter, handle_url))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~url_filter & ~filters.COMMAND, handle_text))
    application.add_handler(MessageReactionHandler(handle_reaction))

    application.post_init = post_init

    print("Starting Telegram Bot (Phase 4 Delivery Tasks)...")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

