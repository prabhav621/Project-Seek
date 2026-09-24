import os
import tempfile
import urllib.request
from apify_client import ApifyClient
from src.ingestion.media import transcribe_media

def extract_instagram_content(url: str) -> str:
    """
    Extracts Instagram Reel/Post data using the Apify enterprise scraper.
    Bypasses all local IP blocking and walled gardens.
    """
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        return "ERROR: APIFY_API_TOKEN is missing from .env file."
        
    print(f"Triggering Apify Extraction for: {url}")
    print("Waiting for Apify cloud servers (usually takes 10-20 seconds)...")
    
    client = ApifyClient(token)
    
    run_input = {
        "directUrls": [url],
        "resultsType": "details",
        "resultsLimit": 1
    }
    
    try:
        # Run the actor on Apify's servers
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        
        video_url = None
        caption = ""
        
        # Iterate over the dataset
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            video_url = item.get('videoUrl')
            caption = item.get('caption', '')
            break # We only expect 1 item
            
        if not video_url:
            return f"ERROR: Apify could not extract a video URL for {url}. It may not be a valid video/reel."
            
        # Download the video locally to a temp file so we can transcribe it
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmpfile:
            print("Video URL retrieved. Downloading for transcription...")
            urllib.request.urlretrieve(video_url, tmpfile.name)
            audio_path = tmpfile.name
            
        # Transcribe
        transcript = ""
        if os.path.exists(audio_path):
            print("Transcribing Instagram audio with Gemini...")
            try:
                transcript = transcribe_media(audio_path)
            except Exception as e:
                print(f"Transcription failed: {e}")
            finally:
                os.remove(audio_path) # Clean up temp file
                
        # Combine
        combined = []
        if caption:
            combined.append(f"Caption:\n{caption}")
        if transcript:
            combined.append(f"Transcript:\n{transcript}")
            
        return "\n\n".join(combined)
        
    except Exception as e:
        return f"Error extracting instagram data via Apify: {str(e)}"
