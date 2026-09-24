import logging
from src.config import settings, TaskType
from src.utils.retry import generate_content_async_with_retry
from google import genai

logger = logging.getLogger(__name__)

class UniversalTranslator:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.get_model_for_task(TaskType.TAGGING).value # Flash-Lite is perfect for fast translation

    async def force_english(self, text: str) -> str:
        if not text or len(text.strip()) == 0:
            return text
            
        prompt = (
            "You are a translation engine. Your task is to ensure the following text is in English.\n"
            "RULES:\n"
            "1. If the text is already entirely or mostly in English, return it EXACTLY as it is, without any modifications, summaries, or added commentary.\n"
            "2. If the text is in another language (e.g., Hindi, Spanish), translate it into highly accurate English, preserving the original formatting.\n"
            "3. Output ONLY the resulting text.\n\n"
            f"TEXT:\n{text}"
        )
        
        try:
            # We don't truncate because Gemini 1.5 Flash has a 1M token context window.
            response = await generate_content_async_with_retry(
                self.client,
                model=self.model,
                contents=prompt
            )
            
            result = response.text.strip()
            if result:
                return result
            return text
        except Exception as e:
            logger.error(f"Universal translation failed: {e}")
            return text # Fallback to original text if API fails
