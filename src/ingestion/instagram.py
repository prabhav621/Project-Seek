import os
import tempfile
import yt_dlp
from src.ingestion.media import transcribe_media

def extract_instagram_content(url: str) -> str:
    """
    Downloads Instagram Reel/Post audio using yt-dlp and transcribes it using Gemini.
    Also attempts to grab the caption from yt-dlp metadata.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = os.path.join(tmpdir, '%(id)s.%(ext)s')
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'quiet': True,
        }
        
        # Inject Instagram cookies to bypass the walled garden
        cookie_path = 'ig_cookies.txt'
        if os.path.exists(cookie_path):
            ydl_opts['cookiefile'] = cookie_path
        
        caption = ""
        audio_path = None
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                caption = info.get('description', '')
                
                # Find the downloaded file
                for f in os.listdir(tmpdir):
                    audio_path = os.path.join(tmpdir, f)
                    break
            except Exception as e:
                return f"Error extracting instagram data: {str(e)}"
                
        transcript = ""
        if audio_path and os.path.exists(audio_path):
            print(f"Transcribing Instagram audio: {audio_path}")
            try:
                transcript = transcribe_media(audio_path)
            except Exception as e:
                print(f"Transcription failed: {e}")
                
        # Combine caption and transcript
        combined = []
        if caption:
            combined.append(f"Caption:\n{caption}")
        if transcript:
            combined.append(f"Transcript:\n{transcript}")
            
        return "\n\n".join(combined)
