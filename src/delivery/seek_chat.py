from src.utils.llm_client import generate_chat_sync, generate_completion_sync
import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from src.config import settings, TaskType
from src.models import DailyItemResponse

logger = logging.getLogger(__name__)

class DriftSummary(BaseModel):
    summary: str = Field(description="A brief summary of the conversation.")
    key_insights: List[str] = Field(description="Key insights or conclusions reached by the Founder.")
    domain_shifts: List[str] = Field(description="Any domains or topics the Founder showed increased interest in.")

class SeekChat:
    def __init__(
        self, 
        context_item: DailyItemResponse, 
        top_domains: List[str], 
        api_key: Optional[str] = None
    ):
        """
        Initializes the SeekChat multi-turn Socratic dialogue manager.
        Uses LiteLLM for multi-provider routing instead of direct Google SDK.
        """
        self.context_item = context_item
        self.top_domains = top_domains
        self.turn_count = 0
        self.max_turns = 10
        self.is_finished = False
        
        self.model = settings.get_model_for_task(TaskType.SEEK_CHAT).value
        
        # Build system instruction
        context_text = (
            self.context_item.context or 
            self.context_item.kata_question or 
            self.context_item.title or 
            "No context provided."
        )
        
        self.system_instruction = (
            "You are Seek, an autonomous intelligence engine engaging the Founder in a Socratic dialogue. "
            "Your goal is not just to provide answers, but to ask probing, multi-directional questions "
            "that push the Founder to synthesize knowledge and uncover blind spots.\n\n"
            f"Context (Daily Item): {context_text}\n\n"
            f"Founder's Top 5 Interest Domains: {', '.join(self.top_domains)}\n\n"
            "Guidelines:\n"
            "- Incorporate the Founder's interest domains into analogies where appropriate.\n"
            "- Keep responses concise and focused.\n"
            "- End your responses with a challenging question.\n"
            "- Do not be overly sycophantic. Challenge assumptions."
        )
        
        # Manual history management for multi-turn chat via LiteLLM
        self.message_history = []

    def send_message(self, message: str) -> str:
        """
        Sends a message to the chat session and returns the AI's response.
        Enforces the 10-turn limit.
        """
        if self.is_finished:
            return "The conversation has already concluded. Please summarize or start a new chat."
            
        if self.turn_count >= self.max_turns:
            self.is_finished = True
            return "Conversation limit reached (10 turns). Please call summarize_conversation()."
            
        self.turn_count += 1
        
        try:
            self.message_history.append({"role": "user", "content": message})
            
            response_text = generate_chat_sync(
                model=self.model,
                messages=self.message_history,
                system_instruction=self.system_instruction,
                temperature=0.7,
            )
            
            self.message_history.append({"role": "assistant", "content": response_text})
            
            if self.turn_count >= self.max_turns:
                self.is_finished = True
                
            return response_text
        except Exception as e:
            logger.error(f"Failed to send message to SeekChat: {e}")
            raise
            
    def summarize_conversation(self) -> DriftSummary:
        """
        Summarizes the 10-turn conversation to be fed back into the Drift Engine.
        """
        system_instruction = (
            "You are an AI behavior analyst. Summarize the preceding Socratic conversation. "
            "Focus on the core arguments, what the Founder synthesized, and any implicit "
            "shifts in interest towards specific domains. "
            "Output strictly as valid JSON with keys: summary (string), key_insights (list of strings), domain_shifts (list of strings)."
        )
        
        # Build history text
        history_text = "Chat History:\n"
        for msg in self.message_history:
            role = "Founder" if msg["role"] == "user" else "Seek"
            history_text += f"{role}: {msg['content']}\n"
        
        prompt = (
            f"{history_text}\n\n"
            "Analyze the conversation and provide the structured JSON summary."
        )
        
        try:
            text = generate_completion_sync(
                model=self.model,
                contents=prompt,
                system_instruction=system_instruction,
                temperature=0.2,
                json_mode=True,
            )
            
            return DriftSummary.model_validate_json(text)
                
        except Exception as e:
            logger.error(f"Failed to summarize conversation: {e}")
            raise
