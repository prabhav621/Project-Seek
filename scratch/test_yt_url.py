import sys, time
from google import genai
from google.genai import types
from src.config import settings

client = genai.Client(api_key=settings.gemini_api_key,
                      http_options=types.HttpOptions(timeout=180_000))
ids = sys.argv[1:] or ["JpgngW1mv1Y", "jNQXAC9IVRw"]
for vid in ids:
    t = time.time()
    try:
        r = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[types.Content(parts=[
                types.Part(file_data=types.FileData(file_uri=f"https://www.youtube.com/watch?v={vid}")),
                types.Part(text="Transcribe the spoken audio of this video verbatim. Do not summarize."),
            ])],
        )
        txt = r.text or ""
        print(f"[OK] {vid} {time.time()-t:.0f}s chars={len(txt)} :: {txt[:200]!r}")
    except Exception as e:
        print(f"[FAIL] {vid} {time.time()-t:.0f}s :: {str(e)[:300]}")
