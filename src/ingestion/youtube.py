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


import threading

# Heavy audio downloads/uploads are limited to 2 at a time (extraction runs in worker threads).
_AUDIO_FALLBACK_SEMAPHORE = threading.Semaphore(2)
_AUDIO_DOWNLOAD_TIMEOUT_S = 300
_GEMINI_UPLOAD_TIMEOUT_MS = 180_000
_GEMINI_URL_TIMEOUT_MS = 300_000


def _extract_via_gemini_url(video_id: str) -> str:
    """Let Gemini fetch and transcribe the YouTube video server-side (preview feature).
    Nothing is downloaded or uploaded by us, so it uses no server/proxy bandwidth."""
    from google import genai
    from google.genai import types
    from src.config import settings, ModelTier
    from src.utils.retry import generate_content_with_retry

    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=_GEMINI_URL_TIMEOUT_MS),
    )
    raw_model = ModelTier.FLASH_LITE.value.replace("gemini/", "")
    response = generate_content_with_retry(
        client=client,
        model=raw_model,
        contents=[types.Content(parts=[
            types.Part(file_data=types.FileData(
                file_uri=f"https://www.youtube.com/watch?v={video_id}")),
            types.Part(text=(
                "Transcribe the spoken audio of this video verbatim. Do not summarize.\n"
                "If the audio is not in English, translate the transcript into English.")),
        ])],
    )
    text = (response.text or "").strip()
    if len(text) < 50:
        raise ValueError(f"Gemini returned an empty/too-short transcript for {video_id}")
    return text


def _extract_via_audio_fallback(video_id: str) -> str:
    with _AUDIO_FALLBACK_SEMAPHORE:
        return _extract_via_audio_fallback_inner(video_id)


def _extract_via_audio_fallback_inner(video_id: str) -> str:
    import subprocess
    import tempfile
    import os
    from google import genai
    from google.genai import types
    from src.config import settings, ModelTier
    from src.utils.retry import generate_content_with_retry
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "-o", output_template,
            f"https://www.youtube.com/watch?v={video_id}"
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=_AUDIO_DOWNLOAD_TIMEOUT_S)
        
        audio_file = None
        for f in os.listdir(tmpdir):
            if f.startswith(video_id):
                audio_file = os.path.join(tmpdir, f)
                break
                
        if not audio_file:
            raise Exception("yt-dlp did not produce an audio file")
            
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=_GEMINI_UPLOAD_TIMEOUT_MS),
        )
        logger.info(f"Uploading {audio_file} to Gemini for native transcription...")
        gemini_file = client.files.upload(file=audio_file)
        
        try:
            prompt = (
                "Please provide a highly accurate transcription of the audio in this file.\n"
                "Do not summarize. Just provide the raw text of what is spoken.\n"
                "If the audio is not in English, translate the transcript into English."
            )
            raw_model = ModelTier.FLASH_LITE.value.replace("gemini/", "")
            
            logger.info(f"Generating transcript with Gemini 3.5 Flash-Lite...")
            response = generate_content_with_retry(
                client=client,
                model=raw_model,
                contents=[gemini_file, prompt]
            )
            return response.text
        finally:
            try:
                client.files.delete(name=gemini_file.name)
            except Exception as e:
                logger.warning(f"Failed to delete Gemini file {gemini_file.name}: {e}")


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

    e4 = None
    try:
        logger.info(f'Falling back to Gemini direct YouTube URL transcription for {video_id}...')
        return _extract_via_gemini_url(video_id)
    except Exception as exc4:
        e4 = exc4
        logger.warning(f'Gemini direct-URL failed for {video_id}: {str(exc4)[:100]}')

    e3 = None
    try:
        logger.info(f'Falling back to Gemini 3.5 Flash-Lite native audio transcription for {video_id}...')
        return _extract_via_audio_fallback(video_id)
    except Exception as exc3:
        e3 = exc3
        logger.warning(f'Audio fallback failed for {video_id}: {str(exc3)[:100]}')

    msg1 = str(e1)[:100] if e1 else 'None'
    msg2 = str(e2)[:100] if e2 else 'None'
    msg3 = str(e3)[:100] if e3 else 'None'
    msg4 = str(e4)[:100] if e4 else 'None'
    raise ValueError(
        f'Failed to fetch transcript for {video_id}. '
        f'Transcript-API: {msg1} | yt-dlp: {msg2} | Gemini-URL: {msg4} | Audio: {msg3}'
    )
