import urllib.parse
import os
import tempfile
import time
import logging
from pathlib import Path
from src.config import settings

logger = logging.getLogger(__name__)

# ─── Video ID Extraction ──────────────────────────────────────────

def _extract_video_id(url: str) -> str:
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

# ─── Primary: youtube-transcript-api ─────────────────────────────────

def _extract_via_transcript_api(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi
    
    proxy_url = getattr(settings, 'residential_proxy_url', '')
    if proxy_url:
        import requests
        session = requests.Session()
        session.proxies = {'http': proxy_url, 'https': proxy_url}
        ytt_api = YouTubeTranscriptApi(http_client=session)
    else:
        ytt_api = YouTubeTranscriptApi()
        
    transcript_list = ytt_api.list(video_id)

    try:
        transcript = transcript_list.find_transcript(['en'])
    except Exception:
        transcript = transcript_list.find_transcript(
            [t.language_code for t in transcript_list]
        )

    transcript_data = transcript.fetch()
    full_text = ' '.join(
        str(t.get('text', '')) if isinstance(t, dict) else str(getattr(t, 'text', ''))
        for t in transcript_data
    )
    return full_text

# ─── Fallback: yt-dlp subtitle extraction ────────────────────────────

def _extract_via_ytdlp(video_id: str) -> str:
    import yt_dlp

    url = f'https://www.youtube.com/watch?v={video_id}'

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

        proxy_url = getattr(settings, 'residential_proxy_url', '')
        if proxy_url:
            ydl_opts['proxy'] = proxy_url

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        sub_files = list(Path(tmpdir).glob('*.vtt')) + list(Path(tmpdir).glob('*.srt'))
        if not sub_files:
            raise ValueError(f'yt-dlp could not extract subtitles for {video_id}')

        raw = sub_files[0].read_text(encoding='utf-8', errors='replace')
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
                continue
            if '-->' in line:
                continue
            if line.isdigit():
                continue
            import re
            clean = re.sub(r'<[^>]+>', '', line)
            if clean and clean not in lines[-1:]:
                lines.append(clean)

        return ' '.join(lines)

# ─── Public API ──────────────────────────────────────────────────────

def extract_subtitles(url: str) -> str:
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f'Could not extract video ID from {url}')

    e1 = None
    e2 = None

    for attempt in range(3):
        try:
            return _extract_via_transcript_api(video_id)
        except Exception as exc1:
            e1 = exc1
            logger.warning(f'Transcript-api failed for {video_id} (Attempt {attempt+1}/3): {str(exc1)[:100]}')

    for attempt in range(2):
        try:
            logger.info(f'Falling back to yt-dlp for {video_id} (Attempt {attempt+1}/2)...')
            return _extract_via_ytdlp(video_id)
        except Exception as exc2:
            e2 = exc2
            logger.warning(f'yt-dlp failed for {video_id} (Attempt {attempt+1}/2): {str(exc2)[:100]}')

    msg1 = str(e1)[:100] if e1 else 'None'
    msg2 = str(e2)[:100] if e2 else 'None'
    raise ValueError(
        f'Failed to fetch transcript for {video_id}. '
        f'Transcript-API: {msg1} | yt-dlp: {msg2}'
    )
