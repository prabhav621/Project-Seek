from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from src.config import settings, TaskType

client = genai.Client(api_key=settings.gemini_api_key)

class DeepKataResponse(BaseModel):
    title: str = Field(description="A catchy title for the Kata")
    context: str = Field(description="The situation or scenario")
    crisis: str = Field(description="The problem that needs solving")
    architecture: str = Field(description="The constraints or current architecture/setup")
    kata_question: str = Field(description="The hypothetical scenario question for the user to solve")
    mirror_question: str = Field(description="A question asking if this reminds them of their own work")

class QuickKataResponse(BaseModel):
    title: str = Field(description="A short title")
    context: str = Field(description="Short context, max 2 sentences")
    kata_question: str = Field(description="The challenge question with a tight constraint")

def generate_deep_kata(raw_content: str, domain: str) -> DeepKataResponse:
    """
    Generates a Deep Kata (configured via ModelTier in config.py) based on raw content and a target domain.
    Deep katas need a scenario, crisis, architecture, and question.
    """
    model_name = settings.get_model_for_task(TaskType.DEEP_KATA).value
    prompt = f"""
    You are an expert AI shaping a "Deep Kata" for a tech founder.
    Based on the following content and domain '{domain}', generate a Deep Kata.
    A Deep Kata is a challenging hypothetical scenario based on real-world engineering, growth, or product crises.
    
    Content:
    {raw_content}
    
    Output strictly as structured JSON matching the requested schema.
    """
    from src.utils.retry import generate_content_with_retry
    response = generate_content_with_retry(
        client,
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DeepKataResponse,
            temperature=0.7,
        ),
    )
    return DeepKataResponse.model_validate_json(response.text)

def generate_quick_kata(raw_content: str, domain: str) -> QuickKataResponse:
    """
    Generates a Quick Kata (configured via ModelTier in config.py) based on raw content and a target domain.
    Quick katas are shorter 2-sentence constraints.
    """
    model_name = settings.get_model_for_task(TaskType.QUICK_KATA).value
    prompt = f"""
    You are an expert AI shaping a "Quick Kata" for a tech founder.
    Based on the following content and domain '{domain}', generate a Quick Kata.
    A Quick Kata is a short, maximum 2-sentence constraint challenge based on real-world situations.
    
    Content:
    {raw_content}
    
    Output strictly as structured JSON matching the requested schema.
    """
    from src.utils.retry import generate_content_with_retry
    response = generate_content_with_retry(
        client,
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QuickKataResponse,
            temperature=0.7,
        ),
    )
    return QuickKataResponse.model_validate_json(response.text)
