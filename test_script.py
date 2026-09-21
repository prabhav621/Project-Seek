import sys
from src.ingestion.youtube import _extract_via_transcript_api

print("Testing youtube-transcript-api with your cookies...")

try:
    text = _extract_via_transcript_api('dQw4w9WgXcQ')
    print('? TRANSCRIPT FETCHED SUCCESSFULLY!')
    print(f'Length of transcript: {len(text)} characters')
    print('Snippet:', text[:100], '...')
except Exception as e:
    print('? TRANSCRIPT API FAILED (IP is still blocked):', e)
    sys.exit(1)
