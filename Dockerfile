FROM python:3.13-slim

# Install system dependencies including ffmpeg for yt-dlp
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Command to run the bot
CMD ["python", "-u", "src/delivery/telegram_bot.py"]

EXPOSE 7860
