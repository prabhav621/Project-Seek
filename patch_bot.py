import sys
with open('src/delivery/telegram_bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
if 'from telegram.ext import CommandHandler' not in content:
    content = content.replace('MessageHandler, filters, MessageReactionHandler', 'MessageHandler, filters, MessageReactionHandler, CommandHandler')

if 'from apscheduler.schedulers.asyncio import AsyncIOScheduler' not in content:
    content = "from apscheduler.schedulers.asyncio import AsyncIOScheduler\nimport pytz\n" + content

# Add the /forge command handler
forge_handler = '''
async def handle_forge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔨 Forging your daily digest... This might take 30-60 seconds.")
    import subprocess
    import sys
    subprocess.Popen([sys.executable, "src/jobs/forge_builder.py"])
'''
if 'def handle_forge' not in content:
    content = content.replace('async def post_init', forge_handler + '\n\nasync def post_init')

# Add scheduler to post_init
scheduler_code = '''
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Kolkata'))
    def run_forge():
        import subprocess
        import sys
        subprocess.Popen([sys.executable, "src/jobs/forge_builder.py"])
    
    scheduler.add_job(run_forge, 'cron', hour=8, minute=0)
    scheduler.start()
    print("⏰ Daily Forge Scheduler started for 8:00 AM IST")
'''
if 'scheduler = AsyncIOScheduler' not in content:
    content = content.replace('asyncio.create_task(_ingestion_worker(application.bot))', 'asyncio.create_task(_ingestion_worker(application.bot))\n' + scheduler_code)

# Add handler to main()
if 'application.add_handler(CommandHandler("forge", handle_forge))' not in content:
    content = content.replace('application.add_handler(MessageReactionHandler(handle_reaction))', 'application.add_handler(MessageReactionHandler(handle_reaction))\n    application.add_handler(CommandHandler("forge", handle_forge))')

with open('src/delivery/telegram_bot.py', 'w', encoding='utf-8') as f:
    f.write(content)
