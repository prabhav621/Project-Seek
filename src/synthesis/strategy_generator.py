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

    async def find_brick_and_source(self, brick_text: str, db) -> tuple:
        """Locates the NeutralBrick and its parent ContentItem from a Telegram brick message snippet."""
        from src.db.models import NeutralBrick, ContentItem
        from sqlalchemy import select

        if not db or not brick_text:
            return None, None

        clean_text = str(brick_text).strip()

        # If replying to a /source card itself
        if "Original Source Record" in clean_text or "Source URL:" in clean_text:
            url_match = re.search(r'Source URL:\s*(\S+)', clean_text)
            if url_match:
                c_url = url_match.group(1).strip()
                c_stmt = select(ContentItem).filter(ContentItem.source_url == c_url).limit(1)
                content_item = (await db.execute(c_stmt)).scalars().first()
                if content_item:
                    b_stmt = select(NeutralBrick).filter(NeutralBrick.source_content_id == content_item.id).limit(1)
                    brick = (await db.execute(b_stmt)).scalars().first()
                    return brick, content_item

        # 1. Extract Thesis snippet from brick text
        thesis_snippet = None
        if "Core Thesis:" in clean_text:
            part = clean_text.split("Core Thesis:", 1)[1]
            for delimiter in ["Mechanics:", "<b>Mechanics:", "Pointers:", "<b>Pointers:"]:
                if delimiter in part:
                    part = part.split(delimiter, 1)[0]
            thesis_snippet = part.strip()

        brick = None
        if thesis_snippet:
            clean_snippet = thesis_snippet.replace("<b>", "").replace("</b>", "").strip().split("\n")[0]
            if len(clean_snippet) > 15:
                stmt = select(NeutralBrick).filter(NeutralBrick.core_thesis.contains(clean_snippet[:50])).limit(1)
                brick = (await db.execute(stmt)).scalars().first()

        # Fallback: if not found by partial match, try latest brick
        if not brick:
            stmt = select(NeutralBrick).order_by(NeutralBrick.created_at.desc()).limit(1)
            brick = (await db.execute(stmt)).scalars().first()

        content_item = None
        if brick and brick.source_content_id:
            c_stmt = select(ContentItem).filter(ContentItem.id == brick.source_content_id).limit(1)
            content_item = (await db.execute(c_stmt)).scalars().first()

        return brick, content_item

    async def ask_brick(self, brick_text: str, question: str, db=None, focus_state: Optional[str] = None) -> Optional[str]:
        """
        Contextually spars with the Founder on a specific Neutral Brick using the PRO Tier.
        If db is provided, retrieves the original raw source transcript to enable deep-dive answering.
        """
        system_prompt = self.build_system_prompt(focus_state)
        system_prompt += f"\n\n{CPO_VOICE_PROMPT}\nThe Founder is asking a specific question, pushing back, or deep-diving into the provided Neutral Brick. Answer directly with precision and high agency."

        source_context = ""
        if db:
            try:
                brick, content_item = await self.find_brick_and_source(brick_text, db)
                if content_item and content_item.raw_text:
                    system_prompt += "\n\nORIGINAL RAW TRANSCRIPT & SOURCE CONTEXT AVAILABLE:\nYou have direct access to the complete unedited raw transcript / source article from which this Neutral Brick was extracted. If the Founder asks for specific details, quotes, numbers, speaker reasoning, or deep dives beyond the concise summary, analyze the raw transcript and quote or cite the source directly."
                    raw_excerpt = content_item.raw_text[:15000]
                    source_context = f"\n\nORIGINAL SOURCE METADATA:\n- Title: {content_item.title}\n- URL: {content_item.source_url}\n- Author / Speaker: {content_item.author or 'Unknown'}\n- Platform: {content_item.source_type}\n\nORIGINAL RAW TRANSCRIPT (UP TO 15,000 CHARS):\n{raw_excerpt}"
            except Exception as e:
                logger.warning(f"Could not load source context for ask_brick: {e}", exc_info=True)

        user_content = f"NEUTRAL BRICK:\n{brick_text}{source_context}\n\nFOUNDER QUESTION: {question}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
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

    async def spar_kata(
        self,
        forge_text: str,
        user_message: str,
        db=None,
        focus_state: Optional[str] = None
    ) -> Optional[str]:
        """
        Disambiguates which Kata the Founder is addressing, retrieves relevant
        vault knowledge (Librarian), and spars as an incisive CPO co-founder.
        """
        retrieved_context = ""
        if db:
            try:
                from src.ingestion.embedder import get_embedder
                from src.db.models import ContentItem, NeutralBrick
                from sqlalchemy import select

                embedder = get_embedder()
                search_query = f"{user_message} {forge_text[:400]}"
                query_vector = await embedder.embed_text(search_query)

                search_results = (await db.execute(
                    select(ContentItem)
                    .filter(ContentItem.embedding != None)
                    .order_by(ContentItem.embedding.cosine_distance(query_vector))
                    .limit(2)
                )).scalars().all()

                blocks = []
                for item in search_results:
                    brick = (await db.execute(select(NeutralBrick).filter(NeutralBrick.source_content_id == item.id))).scalar_one_or_none()
                    if brick:
                        blocks.append(f"Title: {item.title}\nThesis: {brick.core_thesis}\nPointers: {brick.critical_pointers}")
                if blocks:
                    retrieved_context = "\n\n".join(blocks)
            except Exception as embed_e:
                logger.warning(f"Librarian retrieval for Kata sparring failed: {embed_e}")

        global_context = self._read_file(self.mission_directive_path)
        system_prompt = f"""GLOBAL MISSION DIRECTIVE:
{global_context}

ROLE:
You are the incisive CPO and tactical sparring partner. The Founder is replying to a Daily Forge that contains Quick Katas.

FORGE CONTEXT (CONTAINS QUICK KATAS):
{forge_text}
"""
        if retrieved_context:
            system_prompt += f"""
RELEVANT VAULT RETRIEVAL (From Founder's 514 Neutral Bricks):
{retrieved_context}
"""
        system_prompt += f"""
{CPO_VOICE_PROMPT}

DISAMBIGUATION & SPARRING RULES:
1. IDENTIFY THE KATA: The Daily Forge presents multiple Katas (e.g. Quick Kata #1 and Quick Kata #2). You MUST begin by explicitly identifying which Kata the Founder is answering (e.g., "On Kata #1 (Title):" or "On Kata #2:"). Never confuse or conflate them. If the Founder addressed both, address both distinctly.
2. SPARRING OR LIBRARIAN GUIDANCE:
   - If the Founder submitted an answer or solution: Stress-test it immediately. Acknowledge what works, but aggressively expose their biggest blind spot, fragile assumption, or execution bottleneck.
   - If the Founder asked what their notes say or for guidance: Synthesize the practical answer directly from the retrieved knowledge base bricks.
   - Cross-reference their vault's principles whenever applicable.
3. Strict limit: Under 100 words in punchy CPO prose. End with one forward-looking question or immediate next move.
"""
        if focus_state:
            system_prompt += f"\n🎯 ACTIVE FOCUS STATE: {focus_state}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"FOUNDER REPLY:\n{user_message}"}
        ]

        try:
            return await generate_completion_async(Tier.PRO.value, messages=messages, temperature=0.7)
        except Exception as e:
            logger.error(f"Kata sparring failed: {e}")
            return "I hit a temporary issue evaluating this Kata. Send your thought again in a moment!"

