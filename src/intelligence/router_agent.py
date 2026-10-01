import json
import logging
from typing import List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from src.config import settings, ModelTier
from src.utils.retry import generate_content_with_retry

logger = logging.getLogger(__name__)

class RouteMatch(BaseModel):
    matched_id: str
    reasoning: str

def route_reply_sync(reply_text: str, candidate_items: list) -> str:
    """
    Takes the user's reply and a list of candidate DailyItem dictionaries.
    Uses Flash-Lite to determine which item the user is responding to.
    Returns the string ID of the matched item.
    """
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        
        # Strip out massive context to save tokens, just keep the prompts/questions
        slim_candidates = []
        for item in candidate_items:
            challenge = item.get('kata_question') or item.get('mirror_question') or item.get('inversion_prompt') or item.get('context') or ""
            slim_candidates.append({
                'id': str(item['id']),
                'type': item['item_type'],
                'challenge': challenge[:500] if challenge else "No specific challenge text"
            })
            
        system_prompt = """You are a routing agent for a Telegram bot. 
The user was sent a digest containing several intellectual challenges (Katas, Aphorisms, etc).
They replied with a single answer. Your job is to read their answer and determine WHICH challenge they are answering.
Return the 'id' of the matching challenge."""

        prompt = f"User's Reply: {reply_text}\n\nCandidate Challenges:\n{json.dumps(slim_candidates, indent=2)}"
        
        model_name = ModelTier.FLASH_LITE.value.replace("gemini/", "")
        
        response = generate_content_with_retry(
            client=client,
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=RouteMatch,
                temperature=0.1,
            )
        )
        
        result = RouteMatch.model_validate_json(response.text)
        
        # Verify the returned ID actually exists in the candidates to prevent hallucinations
        valid_ids = [c['id'] for c in slim_candidates]
        if result.matched_id in valid_ids:
            return result.matched_id
        else:
            return str(slim_candidates[0]['id'])
            
    except Exception as e:
        logger.error(f"Routing failed, falling back to first item: {e}")
        return str(candidate_items[0]['id'])
