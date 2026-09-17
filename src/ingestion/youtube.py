import urllib.parse
from youtube_transcript_api import YouTubeTranscriptApi

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

def extract_subtitles(url: str) -> str:
    """
    Extracts automatic/manual subtitles from a YouTube video URL using youtube-transcript-api.
    Prefers English subtitles.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from {url}")
        
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        
        # Try to find english transcript (manual or generated)
        try:
            transcript = transcript_list.find_transcript(['en'])
        except Exception:
            # Fallback to whatever is available
            transcript = transcript_list.find_transcript(
                [t.language_code for t in transcript_list]
            )
            
        transcript_data = transcript.fetch()
        
        # Combine text
        full_text = " ".join([t['text'] if isinstance(t, dict) else t.text for t in transcript_data])
        
        return full_text
        
    except Exception as e:
        raise ValueError(f"Failed to fetch transcript: {str(e)}")
