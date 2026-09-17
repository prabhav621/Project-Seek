import json
import logging
from typing import List, Literal, Optional

from pydantic import BaseModel
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class ReplyAnalysisResult(BaseModel):
    agreement_level: Literal["strong_agree", "agree", "neutral", "disagree", "strong_disagree"]
    confidence: float
    topics_mentioned: List[str]
    opinion_expressed: bool
    new_question_asked: bool
    emotional_tone: Literal["excited", "curious", "skeptical", "frustrated", "indifferent"]
    synthesis_quality: Literal["surface", "moderate", "deep"]

class ReplyAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the ReplyAnalyzer.
        If api_key is not provided, it will try to use the GEMINI_API_KEY environment variable.
        """
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-3.6-flash"
        
    def analyze(self, reply_text: str, original_item_text: str = "") -> ReplyAnalysisResult:
        """
        Analyzes a Founder's reply to a Daily Forge item, extracting structured
        sentiments, engagement signals, and context using Gemini 2.5 Flash-Lite.
        
        Args:
            reply_text: The reply message sent by the Founder.
            original_item_text: The text of the item the Founder is replying to (optional, but recommended).
            
        Returns:
            ReplyAnalysisResult: A structured pydantic model with the extracted fields.
        """
        system_instruction = (
            "You are an expert AI behavioral analyst. "
            "Your task is to analyze a user's reply to an AI-generated personalized digest (the 'Daily Forge'). "
            "Extract a structured JSON profile containing the exact schema defined."
        )
        
        prompt = (
            f"Original Item Context (optional):\n{original_item_text}\n\n"
            f"Founder's Reply:\n{reply_text}\n\n"
            "Analyze the Founder's reply and extract the requested fields."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ReplyAnalysisResult,
                    temperature=0.1,
                )
            )
            
            # Use model_validate_json to robustly parse the JSON response text
            # depending on the Pydantic version (v2 uses model_validate_json, v1 uses parse_raw)
            try:
                return ReplyAnalysisResult.model_validate_json(response.text)
            except AttributeError:
                # Fallback for Pydantic v1
                return ReplyAnalysisResult.parse_raw(response.text)
        
        except Exception as e:
            logger.error(f"Failed to analyze reply: {e}")
            raise
