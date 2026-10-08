import os
import re
import logging
from typing import Optional, Dict, Any
from src.config import settings, Tier
from src.utils.llm_client import generate_completion_async

logger = logging.getLogger(__name__)

CPO_VOICE_PROMPT = """
VOICE & STYLE DIRECTIVE:
You are speaking directly to the Founder in Telegram chat as a sharp, incisive strategic co-founder.
- Answer first. Direct, punchy, and concise (Strict limit: under 100 words).
- Speak in natural, clean prose with short paragraphs.
- STRICTLY BANNED: Markdown tables (|---|), developer headers (###), and code blocks (```) unless the user explicitly asked for code/tables.
- Use at most one bold phrase for key emphasis.
- End with one natural, forward-looking question or immediate tactical next step.
"""

def parse_neutral_brick(text: str) -> Dict[str, Any]:
    """
    Tolerant plain-text parser that extracts thesis, mechanics, and pointers.
    Resilient across Gemini, NVIDIA, OpenRouter, and Cloudflare.
    """
    clean_text = text.strip()
    # Strip any focus state tag if prepended
    if "Focus State" in clean_text:
        clean_text = clean_text.split("]", 1)[-1].strip()

    thesis = ""
    mechanics = ""
    pointers = []

    # Look for labelled tags: THESIS:, MECHANICS:, POINTERS:
    thesis_match = re.search(r'(?:THESIS|CORE THESIS):\s*(.*?)(?=\n*(?:MECHANICS|KEY MECHANICS|POINTERS|CRITICAL POINTERS):|$)', clean_text, re.DOTALL | re.IGNORECASE)
    if thesis_match:
        thesis = thesis_match.group(1).strip()

    mechanics_match = re.search(r'(?:MECHANICS|KEY MECHANICS):\s*(.*?)(?=\n*(?:POINTERS|CRITICAL POINTERS):|$)', clean_text, re.DOTALL | re.IGNORECASE)
    if mechanics_match:
        mechanics = mechanics_match.group(1).strip()

    pointers_match = re.search(r'(?:POINTERS|CRITICAL POINTERS):\s*(.*)', clean_text, re.DOTALL | re.IGNORECASE)
    if pointers_match:
        raw_pointers = pointers_match.group(1).strip()
        # Extract lines starting with -, *, or digits
        lines = [line.strip().lstrip("-*•0123456789. ") for line in raw_pointers.splitlines() if line.strip()]
        pointers = [l for l in lines if l]

    # Fallback if the model didn't use strict labels
    if not thesis:
        paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
        thesis = paragraphs[0] if paragraphs else clean_text[:300]
        mechanics = paragraphs[1] if len(paragraphs) > 1 else ""
        pointers = paragraphs[2:] if len(paragraphs) > 2 else []

    return {
        "core_thesis": thesis,
        "key_mechanics": mechanics,
        "critical_pointers": pointers
    }

class DualLayerContextEngine:
    def __init__(self, root_dir: str = "."):
        self.root_dir = root_dir
        self.mission_directive_path = os.path.join(self.root_dir, "mission_directive.md")

    def _read_file(self, path: str) -> str:
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def build_system_prompt(self, focus_state: Optional[str] = None) -> str:
        global_context = self._read_file(self.mission_directive_path)
        if not global_context:
            global_context = "You are a strategic advisor helping the Founder build high-leverage software."

        prompt = f"""GLOBAL MISSION DIRECTIVE:
{global_context}

NEUTRAL BRICK EXTRACTION:
Ruthlessly strip unnecessary sentences, fluff, and build-up. Compress the article into dense, objective pointers (a 'Neutral Brick'). Do not use unnecessary adjectives. Be objective and direct.

OUTPUT FORMAT (STRICT):
THESIS: [1-2 dense sentences capturing the core insight]
MECHANICS: [How and why it works mechanically]
POINTERS:
- [Tactical point 1]
- [Tactical point 2]
- [Tactical point 3]
"""
        if focus_state:
            prompt += f"""
🎯 ACTIVE FOCUS STATE:
The user is currently focused entirely on the following goal:
"{focus_state}"
ALL insights MUST be strictly mapped and constrained to accelerating THIS specific focus goal. Ignore tangents.
"""
        return prompt

    async def generate_strategy(self, content_text: str, focus_state: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Generates a Neutral Brick using the FLASH / LITE Tier (Gemini -> NIM -> Cloudflare)."""
        system_prompt = self.build_system_prompt(focus_state)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract a Neutral Brick from the following content:\n\n{content_text}"}
        ]

        try:
            raw_response = await generate_completion_async(Tier.FLASH.value, messages=messages, temperature=0.2)
            parsed = parse_neutral_brick(raw_response)
            return parsed
        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            return None

    async def apply_lens(self, brick_text: str, lens_name: str, focus_state: Optional[str] = None) -> Optional[str]:
        """Applies an analytical lens to a Neutral Brick using the PRO Tier."""
        global_context = self._read_file(self.mission_directive_path)
        
        # Normalize lens file naming
        clean_name = lens_name.lower().replace("-", "_")
        if clean_name in ["redteam", "red_team"]:
            clean_name = "red_team"
        elif clean_name in ["1stprinciple", "1st_principle", "firstprinciples", "first_principles"]:
            clean_name = "first_principles"
            
        candidate_paths = [
            os.path.join(self.root_dir, "directives", f"{clean_name}.md"),
            os.path.join(self.root_dir, "src", "directives", "lenses", f"{clean_name}.md"),
            os.path.join(self.root_dir, "directives", f"{lens_name}.md")
        ]
        lens_context = ""
        for p in candidate_paths:
            if os.path.exists(p):
                lens_context = self._read_file(p)
                break
                
        if not lens_context:
            lens_context = f"Apply the {clean_name.replace('_', ' ').title()} lens to rigorously analyze this brick."

        system_prompt = f"""GLOBAL MISSION DIRECTIVE:
{global_context}

LENS APPLIED: {clean_name.upper()}
{lens_context}

{CPO_VOICE_PROMPT}
"""
        if focus_state:
            system_prompt += f"\n🎯 ACTIVE FOCUS STATE: {focus_state}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Apply the selected lens to the following Neutral Brick:\n\n{brick_text}"}
        ]

        try:
            return await generate_completion_async(Tier.PRO.value, messages=messages, temperature=0.7)
        except Exception as e:
            logger.error(f"Lens application failed: {e}")
            return "I couldn't apply this lens right now due to a temporary service issue. Ask me again in a moment!"

    async def ask_brick(self, brick_text: str, question: str, focus_state: Optional[str] = None) -> Optional[str]:
        """Contextually spars with the Founder on a specific Neutral Brick using the PRO Tier."""
        system_prompt = self.build_system_prompt(focus_state)
        system_prompt += f"\n\n{CPO_VOICE_PROMPT}\nThe Founder is asking a specific question or pushing back on the provided Neutral Brick. Answer directly using the Brick's context and your reasoning."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"NEUTRAL BRICK:\n{brick_text}\n\nFOUNDER QUESTION: {question}"}
        ]

        try:
            return await generate_completion_async(Tier.PRO.value, messages=messages, temperature=0.7)
        except Exception as e:
            logger.error(f"Ask-the-Brick failed: {e}")
            return "I couldn't process your question against this brick right now. Give me a moment and try again!"

    async def run_librarian(self, query: str, db, focus_state: Optional[str] = None) -> Optional[str]:
        """Performs vector search across ContentItems, gathers NeutralBricks, and synthesizes using PRO Tier."""
        from src.ingestion.embedder import get_embedder
        from src.db.models import ContentItem, NeutralBrick
        from sqlalchemy import select

        embedder = get_embedder()
        query_vector = await embedder.embed_text(query)

        search_results = (await db.execute(
            select(ContentItem)
            .filter(ContentItem.embedding != None)
            .order_by(ContentItem.embedding.cosine_distance(query_vector))
            .limit(3)
        )).scalars().all()

        if not search_results:
            return "Your knowledge base has no indexed content yet. Ingest a few articles first!"

        context_blocks = []
        for item in search_results:
            brick = (await db.execute(select(NeutralBrick).filter(NeutralBrick.source_content_id == item.id))).scalar_one_or_none()
            if brick:
                context_blocks.append(f"Title: {item.title}\nCore Thesis: {brick.core_thesis}\nMechanics: {brick.key_mechanics}\nPointers: {brick.critical_pointers}")
            else:
                context_blocks.append(f"Title: {item.title}\nRaw Snippet: {item.raw_text[:1000]}")

        combined_context = "\n\n---\n\n".join(context_blocks)

        system_prompt = self.build_system_prompt(focus_state)
        system_prompt += f"\n\n{CPO_VOICE_PROMPT}\nYOU ARE THE LIBRARIAN. The Founder is exploring an idea. Synthesize the overlapping patterns from the retrieved bricks. Explain what their accumulated knowledge says about this idea."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"IDEA QUERY: {query}\n\nRETRIEVED KNOWLEDGE BASE BRICKS:\n{combined_context}"}
        ]

        try:
            return await generate_completion_async(Tier.PRO.value, messages=messages, temperature=0.7)
        except Exception as e:
            logger.error(f"Librarian synthesis failed: {e}")
            return "The Librarian hit a temporary issue consulting your knowledge base. Please try asking again in a moment!"
