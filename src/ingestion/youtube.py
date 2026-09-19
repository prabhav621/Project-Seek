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
    ban_keywords = [
        "ip",
        "blocked",
        "requestblocked",
        "ipblocked",
        "too many requests",
        "429",
    ]
    error_lower = error_msg.lower()
    return any(kw in error_lower for kw in ban_keywords)


def _check_circuit_breaker():
    """Raises immediately if the circuit breaker is tripped (IP is banned)."""
    global _circuit_open_until
    if time.time() < _circuit_open_until:
        remaining = int(_circuit_open_until - time.time())
        raise RuntimeError(
            f"⛔ Circuit breaker OPEN — YouTube IP is temporarily banned. "
            f"Auto-retrying in {remaining // 60}m {remaining % 60}s. "
            f"No YouTube requests will be made until then."
        )


def _record_success():
    """Reset the consecutive ban counter on a successful request."""
    global _consecutive_bans
    _consecutive_bans = 0


def _record_ban():
    """Record an IP ban error. Trips the circuit breaker after threshold."""
    global _consecutive_bans, _circuit_open_until
    _consecutive_bans += 1
    if _consecutive_bans >= _BAN_THRESHOLD:
        _circuit_open_until = time.time() + _COOLDOWN_SECONDS
        logger.warning(
            f"🚨 Circuit breaker TRIPPED after {_consecutive_bans} consecutive IP bans. "
            f"All YouTube requests blocked for {_COOLDOWN_SECONDS // 60} minutes."
        )


# ─── Cookie Management ───────────────────────

_COOKIE_PATH = None


def _find_cookies() -> str | None:
    """Locate the cookies.txt file in the project directory."""
    global _COOKIE_PATH
    if _COOKIE_PATH and os.path.exists(_COOKIE_PATH):
        return _COOKIE_PATH

    # Search common locations relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        project_root / "cookies.txt",
        project_root / "yt_cookies.txt",
        Path.home() / "cookies.txt",
    ]
    for path in candidates:
        if path.exists():
            _COOKIE_PATH = str(path)
            logger.info(f"Found YouTube cookies at: {_COOKIE_PATH}")
            return _COOKIE_PATH

    logger.warning("No cookies.txt found. YouTube requests will be unauthenticated (higher ban risk).")
    return None


def _create_authenticated_api():
    """Create a YouTubeTranscriptApi instance with cookie authentication if available."""
    from youtube_transcript_api import YouTubeTranscriptApi

    cookie_path = _find_cookies()
    if cookie_path:
        try:
            import requests as req_lib
            session = req_lib.Session()

            # Load Netscape-format cookies from cookies.txt
            from http.cookiejar import MozillaCookieJar
            cookie_jar = MozillaCookieJar(cookie_path)
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies = cookie_jar

            logger.info("Using authenticated YouTube session (cookies loaded)")
            return YouTubeTranscriptApi(http_client=session)
        except Exception as e:
            logger.warning(f"Failed to load cookies ({e}). Falling back to unauthenticated.")

    return YouTubeTranscriptApi()


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
    return None


# ─── Primary: youtube-transcript-api ──────────

def _extract_via_transcript_api(video_id: str) -> str:
    """Primary method: use youtube-transcript-api with cookie auth."""
    ytt_api = _create_authenticated_api()
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
    """Fallback method: use yt-dlp to download subtitles as files."""
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, '%(id)s')
        cookie_path = _find_cookies()

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

        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path

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
    Extracts subtitles from a YouTube video with multi-layer protection:
    1. Check circuit breaker (fail fast if IP is banned)
    2. Try youtube-transcript-api with cookie auth
    3. Fall back to yt-dlp subtitle extraction
    """
    _check_circuit_breaker()

    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from {url}")

    # Attempt 1: youtube-transcript-api (fast, lightweight)
    try:
        text = _extract_via_transcript_api(video_id)
        _record_success()
        return text
    except Exception as e1:
        error_msg = str(e1)
        is_ban = _is_ip_ban_error(error_msg)

        if is_ban:
            logger.warning(f"IP ban detected on transcript-api for {video_id}: {error_msg}")
            _record_ban()
        else:
            logger.info(f"Transcript-api failed for {video_id} (not IP ban): {error_msg}")

    # Check if circuit breaker just tripped from the ban above
    try:
        _check_circuit_breaker()
    except RuntimeError:
        raise

    # Attempt 2: yt-dlp (heavier, but different request fingerprint)
    try:
        logger.info(f"Falling back to yt-dlp for {video_id}...")
        text = _extract_via_ytdlp(video_id)
        _record_success()
        return text
    except Exception as e2:
        error_msg2 = str(e2)
        if _is_ip_ban_error(error_msg2):
            _record_ban()

        # Both methods failed
        raise ValueError(
            f"Failed to fetch transcript for {video_id}. "
            f"Transcript-API: {str(e1)[:100]} | yt-dlp: {str(e2)[:100]}"
        )
