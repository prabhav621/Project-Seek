import sys
import asyncio
import traceback
from pathlib import Path
from telegram import Update
from telegram.constants import MessageEntityType
from telegram.ext import Application, ContextTypes, MessageHandler, filters, MessageReactionHandler

# Add project root to path
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from src.config import settings
from src.db.session import SessionLocal
from sqlalchemy import select
from src.db.models import DailyItem, InterestVector
from src.intelligence.reply_analyzer import ReplyAnalyzer
from src.intelligence.drift_engine import update_drift
from src.delivery.seek_chat import SeekChat
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
                await bot.send_message(chat_id=job.get("chat_id"), text=f"⚠️ Ingestion job failed: {str(e)[:200]}")
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

        await asyncio.sleep(6)

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
            await bot.send_message(chat_id=chat_id, text=f"❌ Failed to extract playlist {playlist_url}: {str(e)[:200]}")
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

        # ─── Pacing (Gemini RPM Calibration) ──────
        if is_youtube:
            # Gemini Free Tier limit is 15 RPM. 
            # We make TWO calls per video (Embedder + Domain Tagger).
            # 15 RPM / 2 calls = 7.5 videos per min. 60s / 7.5 = 8.0s min delay.
            # 9.0s guarantees we stay safely under the limit.
            delay = 9.0
        else:
            delay = 6

        await asyncio.sleep(delay)

    # ─── Log Failures ──────────────────────────
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
            final_msg += f"\n\n⚠️ {len(failed_urls)} URLs failed. They have been logged to 'failed_ingestions.txt' on the server."
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
                    update_drift(db, str(item.id), 'read')
            await db.commit()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    chat = context.user_data.get('seek_chat')
    if chat and not chat.is_finished:
        response_text = chat.send_message(message.text)
        await message.reply_text(response_text)

        if chat.is_finished:
            summary = chat.summarize_conversation()

            async with SessionLocal() as db:
                for topic in summary.domain_shifts:
                    matched_domain = (await db.execute(select(InterestVector).filter(InterestVector.domain == topic))).scalars().first()
                    if matched_domain:
                        matched_domain.weight = min(1.0, matched_domain.weight + 0.05)
                await db.commit()

            context.user_data['seek_chat'] = None
            await message.reply_text(f"[Seek Chat Concluded]\nSummary: {summary.summary}")
        return

    if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
        original_item_text = message.reply_to_message.text
        reply_text = message.text

        async with SessionLocal() as db:
            latest_item = (await db.execute(select(DailyItem).order_by(DailyItem.created_at.desc()))).scalars().first()
            if not latest_item:
                await message.reply_text("No Daily Forge found to associate this reply with.")
                return

            analyzer = ReplyAnalyzer()
            try:
                analysis = analyzer.analyze(reply_text, original_item_text)
            except Exception as e:
                await message.reply_text("Failed to analyze your reply.")
                return

            engagement = 'debated' if analysis.agreement_level in ['disagree', 'strong_disagree'] else 'responded'
            analysis_dict = analysis.model_dump()

            update_drift(
                db=db,
                item_id=str(latest_item.id),
                engagement_type=engagement,
                reply_analysis=analysis_dict
            )

            latest_item.engagement = engagement
            latest_item.founder_response = reply_text
            latest_item.reply_analysis = analysis_dict
            await db.commit()

            if analysis.new_question_asked:
                top_domains_objs = (await db.execute(select(InterestVector).order_by(InterestVector.weight.desc()).limit(5))).scalars().all()
                top_domains = [td.domain for td in top_domains_objs]
                context_item = DailyItemResponse.model_validate(latest_item)

                chat = SeekChat(context_item=context_item, top_domains=top_domains)
                response_text = chat.send_message(reply_text)
                context.user_data['seek_chat'] = chat

                await message.reply_text(response_text)
            else:
                await message.reply_text("Your insights have been logged. The Forge adjusts.")


async def post_init(application: Application):
    """Start the ingestion worker when the bot starts."""
    global _worker_running
    if not _worker_running:
        asyncio.create_task(_ingestion_worker(application.bot))


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

    application.add_handler(MessageHandler(url_filter, handle_url))
    application.add_handler(MessageHandler(filters.TEXT & ~url_filter & ~filters.COMMAND, handle_text))
    application.add_handler(MessageReactionHandler(handle_reaction))

    application.post_init = post_init

    print("Starting Telegram Bot (Phase 4 Delivery Tasks)...")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
