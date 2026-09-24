import os
import tempfile
import urllib.request
from apify_client import ApifyClient
from src.ingestion.media import transcribe_media

def extract_instagram_content(url: str) -> str:
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
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        
        # Handle dict or object return types depending on apify-client version
        dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else getattr(run, "defaultDatasetId", getattr(run, "default_dataset_id", None))
        
        if not dataset_id:
            return f"ERROR: Could not find defaultDatasetId in the Apify run response."
            
        video_url = None
        caption = ""
        
        for item in client.dataset(dataset_id).iterate_items():
            video_url = item.get('videoUrl')
            caption = item.get('caption', '')
            break 
            
        if not video_url:
            return f"ERROR: Apify could not extract a video URL for {url}. The post might be private, deleted, or age-restricted."
            
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmpfile:
            print("Video URL retrieved. Downloading for transcription...")
            urllib.request.urlretrieve(video_url, tmpfile.name)
            audio_path = tmpfile.name
            
        transcript = ""
        if os.path.exists(audio_path):
            print("Transcribing Instagram audio with Gemini...")
            try:
                transcript = transcribe_media(audio_path)
            except Exception as e:
                print(f"Transcription failed: {e}")
            finally:
                os.remove(audio_path) 
                
        combined = []
        if caption:
            combined.append(f"Caption:\n{caption}")
        if transcript:
            combined.append(f"Transcript:\n{transcript}")
            
        return "\n\n".join(combined)
        
    except Exception as e:
        return f"Error extracting instagram data via Apify: {str(e)}"
