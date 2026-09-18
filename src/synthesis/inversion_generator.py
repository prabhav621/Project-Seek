from src.utils.retry import generate_content_with_retry
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from src.config import settings, TaskType

client = genai.Client(api_key=settings.gemini_api_key)

class InversionResponse(BaseModel):
    inversion_prompt: str = Field(description="The Devil's Advocate prompt challenging comfort zones")

def generate_inversion_prompt(domain: str) -> InversionResponse:
    """
    Generates 'Devil's Advocate' prompts challenging the Founder's comfort zones (configured via ModelTier in config.py).
    """
    model_name = settings.get_model_for_task(TaskType.INVERSION_PROMPT).value
    prompt = f"""
    You are an expert AI shaping a "Devil's Advocate" or Inversion prompt for a solo tech founder.
    The goal is to challenge their comfort zones and force them to think in reverse about the domain '{domain}'.
    Make it thought-provoking, concise, and direct.
    
    Example: "You instinctively build backend-first. What if you built the marketing site before writing a single line of backend code? What would you learn?"
    
    Output strictly as structured JSON matching the requested schema.
    """
    response = generate_content_with_retry(client, 
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InversionResponse,
            temperature=0.8,
        ),
    )
    return InversionResponse.model_validate_json(response.text)
