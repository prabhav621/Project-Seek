from src.utils.retry import generate_content_with_retry
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from src.config import settings, TaskType

client = genai.Client(api_key=settings.gemini_api_key)

class SuggestionHookResponse(BaseModel):
    suggestion_hook: str = Field(description="A short 2-line 'why this' explanation for why the founder should consume this link")

def generate_suggestion_hook(title: str, domain: str) -> SuggestionHookResponse:
    """
    Generates a short 2-line "why this" hook for a curated link (configured via ModelTier in config.py).
    """
    model_name = settings.get_model_for_task(TaskType.SUGGESTION_HOOKS).value
    prompt = f"""
    You are an expert AI curating a reading/watch list for a tech founder.
    Write a short 2-line "why this" hook for the following content title: "{title}".
    The hook should connect the content to their interest in '{domain}'.
    
    Example: "↳ Why this: Matches your interests in growth engineering + investing + Indian tech."
    
    Output strictly as structured JSON matching the requested schema.
    """
    response = generate_content_with_retry(client, 
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SuggestionHookResponse,
            temperature=0.7,
        ),
    )
    return SuggestionHookResponse.model_validate_json(response.text)
