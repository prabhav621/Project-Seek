from src.utils.retry import generate_content_with_retry
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from src.config import settings, TaskType
from typing import Optional

client = genai.Client(api_key=settings.gemini_api_key)

class AphorismResponse(BaseModel):
    quote_text: str = Field(description="The text of the ancient philosophy quote")
    quote_author: str = Field(description="The author of the quote")
    quote_context: str = Field(description="A modern tech/business application anchor for the quote")

def generate_aphorism(domain: str) -> AphorismResponse:
    """
    Selects and contextualizes an ancient philosophy quote for modern tech/business (configured via ModelTier in config.py).
    """
    model_name = settings.get_model_for_task(TaskType.APHORISM).value
    prompt = f"""
    You are an expert AI shaping an "Aphorism" for a tech founder.
    Provide a profound quote from ancient philosophy (Greek, Roman, Indian, etc.).
    Then, contextualize it specifically for modern tech, business, and startups, aligning with the domain '{domain}'.
    
    Output strictly as structured JSON matching the requested schema.
    """
    response = generate_content_with_retry(client, 
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AphorismResponse,
            temperature=0.7,
        ),
    )
    return AphorismResponse.model_validate_json(response.text)

def contextualize_aphorism(quote_text: str, quote_author: str, domain: str) -> AphorismResponse:
    """
    Contextualizes a pre-selected ancient philosophy quote for modern tech/business.
    """
    model_name = settings.get_model_for_task(TaskType.APHORISM).value
    prompt = f"""
    You are an expert AI shaping an "Aphorism" for a tech founder.
    Given the following quote, contextualize it specifically for modern tech, business, and startups, aligning with the domain '{domain}'.
    
    Quote: "{quote_text}"
    Author: {quote_author}
    
    Output strictly as structured JSON matching the requested schema. Ensure quote_text and quote_author are preserved.
    """
    response = generate_content_with_retry(client, 
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AphorismResponse,
            temperature=0.7,
        ),
    )
    return AphorismResponse.model_validate_json(response.text)
