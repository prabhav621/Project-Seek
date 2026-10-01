import os
import logging
import asyncio
from google import genai
from src.config import settings, ModelTier
from src.utils.retry import generate_content_with_retry

logger = logging.getLogger(__name__)

def _extract_document_text_sync(file_path: str, mime_type: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")
        
    client = genai.Client(api_key=settings.gemini_api_key)
    logger.info(f"Uploading {file_path} to Gemini for text extraction...")
    
    # Upload with MIME type explicitly so Gemini handles it properly
    gemini_file = client.files.upload(file=file_path, config={"mime_type": mime_type})
    
    try:
        prompt = (
            "Extract all text from this document accurately.\n"
            "Preserve structure, headings, and formatting using clean Markdown.\n"
            "If there are tables, format them properly in Markdown.\n"
            "If there are images with text, extract the text.\n"
            "Do not summarize, alter, or editorialize the original content."
        )
        raw_model = ModelTier.FLASH_LITE.value.replace("gemini/", "")
        
        response = generate_content_with_retry(
            client=client,
            model=raw_model,
            contents=[gemini_file, prompt]
        )
        return response.text
    finally:
        try:
            client.files.delete(name=gemini_file.name)
        except Exception as e:
            logger.warning(f"Failed to delete Gemini file {gemini_file.name}: {e}")

async def extract_document_text(file_path: str, mime_type: str) -> str:
    return await asyncio.to_thread(_extract_document_text_sync, file_path, mime_type)
