import litellm
import asyncio
from src.config import settings, ModelTier
import os

# Ensure environment variables are loaded for litellm
os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
if settings.groq_api_key:
    os.environ["GROQ_API_KEY"] = settings.groq_api_key
if settings.github_token:
    os.environ["GITHUB_TOKEN"] = settings.github_token
if settings.nvidia_api_key:
    os.environ["NVIDIA_API_KEY"] = settings.nvidia_api_key

async def generate_completion(model: str, contents: str, fallback: bool = True) -> str:
    # Handle Dynamic Context Routing for FLASH tier (Groq has 8k limit)
    estimated_tokens = len(contents) / 4
    
    target_model = model
    # Force route to Gemini if the model is Groq but text is massive
    if "groq" in target_model and estimated_tokens > 7500:
        target_model = ModelTier.FLASH.value
        
    messages = [{"role": "user", "content": contents}]
        
    try:
        response = await litellm.acompletion(
            model=target_model,
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        if fallback and "nvidia/deepseek" in model:
            print(f"Primary PRO node failed ({e}). Falling back to GitHub Models...")
            response = await litellm.acompletion(
                model=ModelTier.PRO_FALLBACK.value,
                messages=messages
            )
            return response.choices[0].message.content
        raise e

async def generate_embedding(model: str, inputs: list[str]) -> list[list[float]]:
    response = await litellm.aembedding(
        model=model,
        input=inputs
    )
    # litellm returns data as a list of dicts with 'embedding'
    return [d["embedding"] for d in response.data]
