from src.utils.retry import generate_content_async_with_retry
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import InterestVector
from src.ingestion.embedder import get_embedder
from google import genai
from src.config import settings, TaskType

class DomainTagger:
    """
    Tags content with interest domains using pgvector cosine similarity.
    If no domains match, triggers an Expanding Universe genesis event to create a new domain.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.embedder = get_embedder()

    async def get_nearest_domains(self, content_embedding: List[float], limit: int = 3, threshold_distance: float = 0.6) -> List[Tuple[str, float]]:
        if len(content_embedding) != 768:
            raise ValueError(f"Content embedding must be 768 dimensions, got {len(content_embedding)}")

        stmt = (
            select(
                InterestVector.domain,
                InterestVector.embedding.cosine_distance(content_embedding).label('distance')
            )
            .where(InterestVector.embedding.is_not(None))
            .order_by(InterestVector.embedding.cosine_distance(content_embedding))
            .limit(limit)
        )

        results = (await self.db.execute(stmt)).all()

        valid_matches = []
        for row in results:
            if row.distance <= threshold_distance:
                valid_matches.append((row.domain, float(row.distance)))

        return valid_matches

    async def trigger_genesis(self, raw_text: str) -> str:
        """
        Uses Gemini to extract a 2-3 word domain name from completely novel text.
        Embeds it and inserts it into the database as a new InterestVector.
        """
        prompt = f"Extract the core domain or theme of the following text in exactly 2 to 3 words. Return ONLY the 2-3 words, lowercase, spaces replaced with underscores (e.g., 'quantum_computing', 'longevity_research').\n\nText:\n{raw_text[:3000]}"
        response = await generate_content_async_with_retry(self.client, 
            model=settings.get_model_for_task(TaskType.TAGGING).value,
            contents=prompt
        )
        new_domain = response.text.strip().lower().replace(" ", "_")
        
        # Check if it somehow exists
        existing = (await self.db.execute(select(InterestVector).filter_by(domain=new_domain))).scalar_one_or_none()
        if not existing:
            # Embed the new domain name
            domain_embedding = await self.embedder.embed_text(new_domain)
            vector = InterestVector(
                domain=new_domain,
                weight=0.30, # Baseline weight for newly discovered domains
                is_blind_spot=False,
                is_graveyard=False,
                embedding=domain_embedding
            )
            self.db.add(vector)
            await self.db.commit()
            print(f"🌌 EXPANDING UNIVERSE: Discovered new domain '{new_domain}'")
        
        return new_domain

    async def tag_content(self, content_embedding: List[float], raw_text: Optional[str] = None, limit: int = 3, threshold_distance: float = 0.6) -> List[str]:
        """
        Convenience method to retrieve just the domain names.
        If no matches are found and raw_text is provided, triggers genesis.
        """
        matches = await self.get_nearest_domains(
            content_embedding, 
            limit=limit, 
            threshold_distance=threshold_distance
        )
        
        domain_names = [match[0] for match in matches]
        
        if not domain_names and raw_text:
            new_domain = await self.trigger_genesis(raw_text)
            domain_names.append(new_domain)
            
        return domain_names
