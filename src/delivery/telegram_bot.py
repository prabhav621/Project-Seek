import sys
import asyncio
from pathlib import Path
from telegram import Update
from telegram.constants import MessageEntityType
from telegram.ext import Application, ContextTypes, MessageHandler, filters, MessageReactionHandler

# Add project root to path
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_path))

from src.config import settings
from src.db.session import SessionLocal
from src.db.models import DailyItem, InterestVector
from src.intelligence.reply_analyzer import ReplyAnalyzer
from src.intelligence.drift_engine import update_drift
from src.delivery.seek_chat import SeekChat
from src.models import DailyItemResponse

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
        
        await message.reply_text(f"Intercepted {len(playlists)} playlists and {len(individual)} individual links.\nQueuing for background ingestion to respect API rate limits...")
        
        if playlists:
            for p in playlists:
                asyncio.create_task(process_playlist_background(p, message.chat_id, context.bot))
                
        if individual:
            asyncio.create_task(process_individual_background(individual, message.chat_id, context.bot))

async def process_individual_background(urls: list, chat_id: int, bot):
    from src.ingestion.parser import UniversalLinkParser
    from src.db.session import SessionLocal
    
    success_count = 0
    fail_count = 0
    
    with SessionLocal() as db:
        parser = UniversalLinkParser(db)
        for url in urls:
            try:
                await parser.process_url(url, ingestion_mode='manual')
                success_count += 1
                print(f"Ingested: {url}")
            except Exception as e:
                fail_count += 1
                print(f"Failed: {url} - {e}")
            
            # RATE LIMITING: 6 seconds per item guarantees we stay under Gemini's 15 RPM free tier limit
            # and prevents Supabase connection spikes or Telegram spam limits.
            await asyncio.sleep(6)
            
    await bot.send_message(chat_id=chat_id, text=f"✅ Batch ingestion completed!\nSuccess: {success_count}\nFailed: {fail_count}")

async def process_playlist_background(playlist_url: str, chat_id: int, bot):
    import yt_dlp
    from src.ingestion.parser import UniversalLinkParser
    from src.db.session import SessionLocal
    
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
        await bot.send_message(chat_id=chat_id, text=f"❌ Failed to extract playlist {playlist_url}: {str(e)}")
        return
        
    print(f"Found {len(video_urls)} videos in playlist. Ingesting...")
    await bot.send_message(chat_id=chat_id, text=f"Found {len(video_urls)} videos in playlist. Starting sequential ingestion (rate-limited to 6s/video)...")
    
    success_count = 0
    fail_count = 0
    
    with SessionLocal() as db:
        parser = UniversalLinkParser(db)
        for v_url in video_urls:
            try:
                await parser.process_url(v_url, ingestion_mode='manual')
                success_count += 1
                print(f"Ingested playlist video: {v_url}")
            except Exception as e:
                fail_count += 1
                print(f"Failed to ingest playlist video {v_url}: {e}")
                
            # RATE LIMITING: 6 seconds per item
            await asyncio.sleep(6)
                
    await bot.send_message(chat_id=chat_id, text=f"✅ Playlist ingestion completed!\nSuccess: {success_count}\nFailed: {fail_count}")


async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reaction = update.message_reaction
    if not reaction:
        return
        
    with SessionLocal() as db:
        latest_item = db.query(DailyItem).order_by(DailyItem.created_at.desc()).first()
        if latest_item:
            items = db.query(DailyItem).filter(DailyItem.forge_date == latest_item.forge_date).all()
            for item in items:
                if item.engagement == 'pending':
                    item.engagement = 'read'
                    update_drift(db, str(item.id), 'read')
            db.commit()


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
            
            with SessionLocal() as db:
                for topic in summary.domain_shifts:
                    matched_domain = db.query(InterestVector).filter(InterestVector.domain == topic).first()
                    if matched_domain:
                        matched_domain.weight = min(1.0, matched_domain.weight + 0.05)
                db.commit()
            
            context.user_data['seek_chat'] = None
            await message.reply_text(f"[Seek Chat Concluded]\nSummary: {summary.summary}")
        return

    if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
        original_item_text = message.reply_to_message.text
        reply_text = message.text

        with SessionLocal() as db:
            latest_item = db.query(DailyItem).order_by(DailyItem.created_at.desc()).first()
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
            db.commit()

            if analysis.new_question_asked:
                top_domains_objs = db.query(InterestVector).order_by(InterestVector.weight.desc()).limit(5).all()
                top_domains = [td.domain for td in top_domains_objs]
                context_item = DailyItemResponse.model_validate(latest_item)
                
                chat = SeekChat(context_item=context_item, top_domains=top_domains)
                response_text = chat.send_message(reply_text)
                context.user_data['seek_chat'] = chat
                
                await message.reply_text(response_text)
            else:
                await message.reply_text("Your insights have been logged. The Forge adjusts.")


import os
from aiohttp import web

async def health_check(request):
    return web.Response(text="Project Seek Bot is ALIVE and healthy.")

async def start_dummy_server(application: Application):
    port = int(os.environ.get("PORT", 7860))
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Dummy web server listening on port {port} for Render health checks.")

def main():
    token = settings.telegram_bot_token
    if not token:
        print("Error: telegram_bot_token is missing from configuration.")
        return

    application = Application.builder().token(token).post_init(start_dummy_server).build()

    url_filter = (
        filters.Entity(MessageEntityType.URL) | 
        filters.Entity(MessageEntityType.TEXT_LINK) | 
        filters.CaptionEntity(MessageEntityType.URL) | 
        filters.CaptionEntity(MessageEntityType.TEXT_LINK)
    )
    
    application.add_handler(MessageHandler(url_filter, handle_url))
    application.add_handler(MessageHandler(filters.TEXT & ~url_filter & ~filters.COMMAND, handle_text))
    application.add_handler(MessageReactionHandler(handle_reaction))

    print("Starting Telegram Bot (Phase 4 Delivery Tasks)...")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
