import os
import json
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import litellm
from src.config import settings, Capability, MODEL_POOLS

logger = logging.getLogger(__name__)

class StrategyBrick(BaseModel):
    core_thesis: str = Field(description="The core thesis compressed into a neutral, dense sentence.")
    key_mechanics: str = Field(description="Objective mechanics of how it works without fluff.")
    critical_pointers: list[str] = Field(description="A list of dense, objective pointers without unnecessary sentences.")


def _get_api_key(model_id: str) -> str:
    from src.config import settings
    if "openrouter" in model_id: return settings.openrouter_api_key
    if "nvidia" in model_id: return settings.nvidia_api_key
    if "gemini" in model_id: return settings.gemini_api_key
    return settings.cloudflare_api_key

def _get_kwargs(model_id: str) -> dict:
    kwargs = {"api_key": _get_api_key(model_id)}
    if "cloudflare" in model_id:
        kwargs["drop_params"] = True
    return kwargs

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
        # 1. Global Context
        global_context = self._read_file(self.mission_directive_path)
        if not global_context:
            global_context = "You are a strategic advisor."

        # Assembly
        prompt = f"""GLOBAL MISSION DIRECTIVE:
{global_context}

NEUTRAL BRICK EXTRACTION:
Ruthlessly strip unnecessary sentences, fluff, and build-up. Compress the article into dense, objective pointers (a 'Neutral Brick'). Do not use unnecessary adjectives. Be objective and direct.\nOUTPUT STRICTLY A RAW JSON DICTIONARY with keys: 'core_thesis' (string), 'key_mechanics' (string), and 'critical_pointers' (list of strings).

"""
        # 3. Ephemeral Focus Context (Highest Priority Overriding Layer)
        if focus_state:
            prompt += f"""
🎯 ACTIVE FOCUS STATE:
The user is currently focused entirely on the following goal:
"{focus_state}"
ALL strategies you extract MUST be strictly mapped, tailored, and constrained to accelerating THIS specific focus goal. Ignore tangents.
IMPORTANT: Because Focus State is active, you MUST strictly prepend your output with the exact string `[❗️ Focus State]`.
"""
        return prompt

    async def generate_strategy(self, content_text: str, focus_state: Optional[str] = None) -> Optional[Dict[str, Any]]:
        # TODO: Add focus_expires_at logic with a 15-minute TTL requirement for the focus_state 
        # so the telegram handler knows when to drop it.
        system_prompt = self.build_system_prompt(focus_state)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract a Strategy Brick from the following content:\n\n{content_text}"}
        ]

        # Use the Fast Creative pool for Strategy Bricks (extraction doesn't require deep logic)
        model_pool = MODEL_POOLS.get(Capability.FAST_CREATIVE, [])
        if not model_pool:
            logger.error("No models available in FAST_CREATIVE pool.")
            return None

        # Linear Fallback Loop
        for model_id in model_pool:
            try:
                logger.info(f"Attempting strategy generation with model: {model_id}")
                kwargs = _get_kwargs(model_id)
                if "cloudflare" not in model_id:
                    kwargs["response_format"] = StrategyBrick

                response = await litellm.acompletion(
                    model=model_id,
                    messages=messages,
                    **kwargs
                )
                
                content = response.choices[0].message.content
                if isinstance(content, str):
                    if 'Focus State' in content:
                        content = content.split(']', 1)[-1].strip()
                    content = content.strip()
                    if content.startswith('`json'): content = content[7:]
                    elif content.startswith('`'): content = content[3:]
                    if content.endswith('`'): content = content[:-3]
                    content = content.strip()
                    import json, re
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        match = re.search(r'\{.*\}', content, re.DOTALL)
                        if match: return json.loads(match.group(0))
                        raise
                else:
                    return content # Already parsed dict

            except Exception as e:
                logger.warning(f"Model {model_id} failed: {str(e)}. Failing over...")
                continue
                
        logger.error("All models in the FAST_CREATIVE pool failed.")
        return None

    async def apply_lens(self, brick_text: str, lens_name: str, focus_state: Optional[str] = None) -> Optional[str]:
        global_context = self._read_file(self.mission_directive_path)
        if not global_context:
            global_context = "You are a strategic advisor."
            
        lens_path = os.path.join(self.root_dir, "src", "directives", "lenses", f"{lens_name}.md")
        lens_context = self._read_file(lens_path)
        if not lens_context:
            lens_context = f"Apply the {lens_name} lens to the analysis."
            
        system_prompt = f"GLOBAL MISSION DIRECTIVE:\n{global_context}\n\nLENS APPLIED: {lens_name.upper()}\n{lens_context}\n\n"
        
        if focus_state:
            system_prompt += f"🎯 ACTIVE FOCUS STATE:\nThe user is currently focused entirely on the following goal:\n\"{focus_state}\"\nALL insights MUST be strictly tailored and constrained to accelerating THIS specific focus goal.\n"
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Apply the selected lens to the following Neutral Brick:\n\n{brick_text}"}
        ]
        
        model_pool = MODEL_POOLS.get(Capability.DEEP_REASONING, [])
        if not model_pool:
            logger.error("No models available in DEEP_REASONING pool.")
            return None
            
        for model_id in model_pool:
            try:
                response = await litellm.acompletion(
                    model=model_id,
                    messages=messages,
                    **_get_kwargs(model_id)
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Model {model_id} failed for apply_lens: {str(e)}. Failing over...")
                continue
                
        logger.error("All models in the DEEP_REASONING pool failed for apply_lens.")
        return None

    
    async def ask_brick(self, brick_text: str, question: str, focus_state: Optional[str] = None) -> Optional[str]:
        system_prompt = self.build_system_prompt(focus_state)
        system_prompt += "\n\nThe user is asking a specific question about the provided Neutral Brick. Answer their question directly using the insights from the brick and your own reasoning."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"NEUTRAL BRICK:\n{brick_text}\n\nUSER QUESTION: {question}"}
        ]
        
        from src.config import MODEL_POOLS, Capability
        import litellm
        model_pool = MODEL_POOLS.get(Capability.DEEP_REASONING, [])
        for model_id in model_pool:
            try:
                kwargs = _get_kwargs(model_id)
                response = await litellm.acompletion(
                    model=model_id,
                    messages=messages,
                    **kwargs
                )
                return response.choices[0].message.content
            except Exception as e:
                continue
        return "Failed to analyze the brick."

    async def run_librarian(self, query: str, db, focus_state: Optional[str] = None) -> Optional[str]:
        """Performs vector search across ContentItems, gathers NeutralBricks, and synthesizes."""
        from src.ingestion.embedder import get_embedder
        from src.db.models import ContentItem, NeutralBrick
        from sqlalchemy import select
        
        embedder = get_embedder()
        query_vector = await embedder.embed_text(query)
        
        # Search for top 3 relevant articles
        search_results = (await db.execute(
            select(ContentItem)
            .filter(ContentItem.embedding != None)
            .order_by(ContentItem.embedding.cosine_distance(query_vector))
            .limit(3)
        )).scalars().all()
        
        if not search_results:
            return "Your knowledge base is empty or has no embedded content yet."
            
        context_blocks = []
        for item in search_results:
            brick = (await db.execute(select(NeutralBrick).filter(NeutralBrick.source_content_id == item.id))).scalar_one_or_none()
            if brick:
                context_blocks.append(f"Title: {item.title}\nCore Thesis: {brick.core_thesis}\nMechanics: {brick.key_mechanics}\nPointers: {brick.critical_pointers}")
            else:
                context_blocks.append(f"Title: {item.title}\nRaw Snippet: {item.raw_text[:1000]}")
                
        combined_context = "\n\n---\n\n".join(context_blocks)
        
        system_prompt = self.build_system_prompt(focus_state)
        system_prompt += "\n\nYOU ARE THE LIBRARIAN. The Founder is exploring a specific idea. I will provide you with highly relevant Neutral Bricks retrieved from their Knowledge Base. Your job is to synthesize these bricks, highlight overlapping patterns, and explain what their Knowledge Base says about this idea. Be ruthless, concise, and profound. DO NOT just summarize the articles individually. Merge them into a single strategic insight."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"IDEA QUERY: {query}\n\nRETRIEVED KNOWLEDGE BASE BRICKS:\n{combined_context}"}
        ]
        
        model_pool = MODEL_POOLS.get(Capability.DEEP_REASONING, [])
        for model_id in model_pool:
            try:
                import litellm
                from src.config import settings
                response = await litellm.acompletion(
                    model=model_id,
                    messages=messages,
                    **_get_kwargs(model_id)
                )
                return response.choices[0].message.content
            except Exception as e:
                continue
                
        return "All reasoning models failed to run the Librarian."
