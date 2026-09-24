import os
import tempfile
import urllib.request
from apify_client import ApifyClient
from src.ingestion.media import transcribe_media, analyze_images

def extract_instagram_content(url: str) -> str:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        return "ERROR: APIFY_API_TOKEN is missing from .env file."
        
    print(f"Triggering Apify Extraction for: {url}")
    print("Waiting for Apify cloud servers (usually takes 10-20 seconds)...")
    
    client = ApifyClient(token)
    run_input = {"directUrls": [url], "resultsType": "details", "resultsLimit": 1}
    
    try:
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        dataset_id = run["defaultDatasetId"] if isinstance(run, dict) else getattr(run, "defaultDatasetId", getattr(run, "default_dataset_id", None))
        
        if not dataset_id:
            return f"ERROR: Could not find defaultDatasetId in the Apify run response."
            
        video_url = None
        image_urls = []
        caption = ""
        
        for item in client.dataset(dataset_id).iterate_items():
            video_url = item.get('videoUrl')
            caption = item.get('caption', '')
            
            # If no video, look for images (carousel support)
            if not video_url:
                if item.get('images') and len(item.get('images')) > 0:
                    image_urls = item.get('images')
                elif item.get('displayUrl'):
                    image_urls = [item.get('displayUrl')]
            break 
            
        if not video_url and not image_urls:
            return f"ERROR: Apify could not extract media for {url}. The post might be private, deleted, or age-restricted."
            
        transcript = ""
        image_text = ""
        
        if video_url:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmpfile:
                print("Video URL retrieved. Downloading for transcription...")
                urllib.request.urlretrieve(video_url, tmpfile.name)
                audio_path = tmpfile.name
            if os.path.exists(audio_path):
                print("Transcribing Instagram audio with Gemini...")
                try:
                    transcript = transcribe_media(audio_path)
                except Exception as e:
                    print(f"Transcription failed: {e}")
                finally:
                    os.remove(audio_path)
                    
        elif image_urls:
            downloaded_paths = []
            print(f"Carousel detected: {len(image_urls)} images. Downloading for OCR...")
            try:
                for idx, img_url in enumerate(image_urls):
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmpfile:
                        urllib.request.urlretrieve(img_url, tmpfile.name)
                        downloaded_paths.append(tmpfile.name)
                
                if downloaded_paths:
                    print(f"Extracting text from {len(downloaded_paths)} slides with Gemini...")
                    image_text = analyze_images(downloaded_paths)
            except Exception as e:
                print(f"Image analysis failed: {e}")
            finally:
                for path in downloaded_paths:
                    if os.path.exists(path):
                        os.remove(path)
                
        combined = []
        if caption:
            combined.append(f"Caption:\n{caption}")
        if transcript:
            combined.append(f"Transcript:\n{transcript}")
        if image_text:
            combined.append(f"Image Content:\n{image_text}")
            
        return "\n\n".join(combined)
        
    except Exception as e:
        return f"Error extracting instagram data via Apify: {str(e)}"
