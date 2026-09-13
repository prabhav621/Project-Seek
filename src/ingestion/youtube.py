import os
import glob
import tempfile
import yt_dlp

def extract_subtitles(url: str) -> str:
    """
    Extracts automatic/manual subtitles from a YouTube video URL using yt-dlp.
    Prefers manual English subtitles, falls back to automatic.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = os.path.join(tmpdir, '%(id)s.%(ext)s')
        ydl_opts = {
            'skip_download': True,       # Skip video download
            'writesubtitles': True,      # Write manual subtitles
            'writeautomaticsub': True,   # Write automatic subtitles
            'subtitleslangs': ['en'],    # Prefer English
            'subtitlesformat': 'vtt/srt/best',
            'quiet': True,
            'outtmpl': outtmpl,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
            except Exception as e:
                return f"Error extracting subtitles: {str(e)}"
        
        # Check for downloaded files in the temporary directory
        subtitle_files = glob.glob(os.path.join(tmpdir, '*.*'))
        if not subtitle_files:
            return ""
            
        # Read the first subtitle file
        try:
            with open(subtitle_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Error reading subtitle file: {str(e)}"
