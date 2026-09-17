# Goal: Resolve YouTube IP Bans on Cloud Hosting (Railway)

The core issue causing the YouTube ingestion failures on Railway is that **YouTube actively blacklists datacenter IP addresses** (Railway, AWS, Google Cloud, Azure) to prevent scraping.

Our logs confirm this:
- yt-dlp returns: HTTP 429: Too Many Requests + Sign in to confirm you're not a bot.
- youtube-transcript-api returns: YouTube is blocking requests from your IP.

Furthermore, youtube-transcript-api recently **disabled cookie authentication entirely** because YouTube's anti-bot changes broke it. Therefore, simply uploading a cookies.txt file is no longer a viable workaround for transcripts.

## User Review Required

We have four architectural options to bypass this block reliably. Please review and approve your preferred path:

### Option 1: Use a Rotating Proxy API (Recommended for Stability)
We integrate a proxy service (like BrightData, ZenRows, ScraperAPI, or Webshare). You would need to sign up for a cheap or free tier and provide a PROXY_URL in the Railway environment variables. youtube-transcript-api and yt-dlp natively support routing traffic through these proxies.

### Option 2: Use a Dedicated YouTube API via RapidAPI
Instead of scraping YouTube ourselves, we hit a dedicated third-party YouTube Subtitle API on RapidAPI (many have generous free tiers, e.g., 500 requests/month). We just add a RAPIDAPI_KEY to our config and swap out the ingestion logic.

### Option 3: Deploy a Free Cloudflare Worker Proxy
We write a tiny script that you deploy for free on Cloudflare Workers. It will act as a middleman, proxying traffic from Railway -> Cloudflare -> YouTube. Cloudflare's residential/edge IPs are often less heavily blocked than Railway's datacenter IPs, though it's not a 100% guarantee against rate-limits.

### Option 4: Host Locally instead of on Railway
If we run the Docker container on your local machine (e.g., your laptop) instead of Railway, the bot will use your home IP address, which YouTube trusts.

## Open Questions

- **Which option (1, 2, 3, or 4) do you prefer?**
- If Option 1 or 2, are you okay with signing up for a free API key on one of those platforms and adding it to your Railway environment variables?

## Proposed Changes

Depending on your choice, we will:

### If Option 1 (Proxy):
#### [MODIFY] src/config.py
Add PROXY_URL environment variable.
#### [MODIFY] src/ingestion/youtube.py
Configure youtube-transcript-api to use the proxy_config parameter.

### If Option 2 (RapidAPI):
#### [MODIFY] src/config.py
Add RAPIDAPI_KEY.
#### [MODIFY] src/ingestion/youtube.py
Replace youtube-transcript-api with a direct HTTP GET request to the chosen RapidAPI endpoint.

## Verification Plan
1. We will push the chosen implementation to GitHub.
2. Railway will auto-deploy.
3. You will forward a new YouTube video to the Telegram bot, and it should successfully download the transcript without the "IP Blocked" error.
