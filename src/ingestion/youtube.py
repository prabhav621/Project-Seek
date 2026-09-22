"""
YouTube transcript extraction with multi-layer IP ban protection:
1. Cookie-authenticated youtube-transcript-api (primary)
2. yt-dlp subtitle extraction (fallback)
3. Circuit breaker (auto-pause on IP ban detection)
"""
import os
import time
import logging
import tempfile
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Circuit Breaker ──────────────────────────
# Prevents the bot from hammering YouTube after an IP ban is detected.
# After 3 consecutive IP ban errors, all YouTube requests are blocked
# for COOLDOWN_SECONDS without making any network calls.

_consecutive_bans = 0
_circuit_open_until = 0.0
_BAN_THRESHOLD = 3
_COOLDOWN_SECONDS = 1800  # 30 minutes


def _is_ip_ban_error(error_msg: str) -> bool:
    """Detect if an error is caused by YouTube IP blocking."""
    import re
    error_lower = error_msg.lower()
    
    # Check for exact exception class names from youtube-transcript-api
    exact_matches = [
        "ipblocked",
        "requestblocked",

# ─── Video ID Extraction ─────────────────────

def _extract_video_id(url: str) -> str:
    """Extracts the video ID from a YouTube URL."""
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            qs = urllib.parse.parse_qs(parsed_url.query)
            return qs.get('v', [None])[0]
        if parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/')[2]
        if parsed_url.path.startswith('/v/'):
            return parsed_url.path.split('/')[2]
        if parsed_url.path.startswith('/shorts/'):
            return parsed_url.path.split('/')[2]
    return None


# ─── Primary: youtube-transcript-api ──────────

def _extract_via_transcript_api(video_id: str) -> str:
    """Primary method: use youtube-transcript-api routed via proxy."""
    from youtube_transcript_api import YouTubeTranscriptApi
    
    proxy_url = getattr(settings, "residential_proxy_url", "")
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    
    ytt_api = YouTubeTranscriptApi(proxies=proxies) if proxies else YouTubeTranscriptApi()
    transcript_list = ytt_api.list(video_id)

    # Try English first
    try:
        transcript = transcript_list.find_transcript(['en'])
    except Exception:
        transcript = transcript_list.find_transcript(
            [t.language_code for t in transcript_list]
        )

    transcript_data = transcript.fetch()
    full_text = " ".join(
        str(t.get('text', '')) if isinstance(t, dict) else str(getattr(t, 'text', ''))
        for t in transcript_data
    )
    return full_text


# ─── Fallback: yt-dlp subtitle extraction ────

def _extract_via_ytdlp(video_id: str) -> str:
    """Fallback method: use yt-dlp via proxy."""
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, '%(id)s')

        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'subtitlesformat': 'vtt',
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'outtmpl': output_template,
        }

        proxy_url = getattr(settings, "residential_proxy_url", "")
        if proxy_url:
            ydl_opts['proxy'] = proxy_url

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the downloaded subtitle file
        sub_files = list(Path(tmpdir).glob('*.vtt')) + list(Path(tmpdir).glob('*.srt'))
        if not sub_files:
            raise ValueError(f"yt-dlp could not extract subtitles for {video_id}")

        # Parse VTT/SRT into plain text
        raw = sub_files[0].read_text(encoding='utf-8', errors='replace')
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            # Skip VTT headers, timestamps, and empty lines
            if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
                continue
            if '-->' in line:
                continue
            if line.isdigit():
                continue
            # Remove VTT tags like <c> </c>
            import re
            clean = re.sub(r'<[^>]+>', '', line)
            if clean and clean not in lines[-1:]:  # basic dedup of repeated lines
                lines.append(clean)

        return ' '.join(lines)


# ─── Public API ───────────────────────────────

def extract_subtitles(url: str) -> str:
    """
    Extracts subtitles from a YouTube video with immediate proxy retry logic.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from {url}")

    e1 = None
    e2 = None

    # Attempt 1: youtube-transcript-api (fast, lightweight, with 3 instant retries)
    for attempt in range(3):
        try:
            return _extract_via_transcript_api(video_id)
        except Exception as exc1:
            e1 = exc1
            logger.warning(f"Transcript-api failed for {video_id} (Attempt {attempt+1}/3): {str(exc1)[:100]}")
            # Instant retry triggers next IP in the proxy pool

    # Attempt 2: yt-dlp (heavier fallback)
    for attempt in range(2):
        try:
            logger.info(f"Falling back to yt-dlp for {video_id} (Attempt {attempt+1}/2)...")
            return _extract_via_ytdlp(video_id)
        except Exception as exc2:
            e2 = exc2
            logger.warning(f"yt-dlp failed for {video_id} (Attempt {attempt+1}/2): {str(exc2)[:100]}")

    msg1 = str(e1)[:100] if e1 else "None"
    msg2 = str(e2)[:100] if e2 else "None"
    raise ValueError(
        f"Failed to fetch transcript for {video_id}. "
        f"Transcript-API: {msg1} | yt-dlp: {msg2}"
    )
