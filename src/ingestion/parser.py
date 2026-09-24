import urllib.parse
from enum import Enum
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import ContentItem
from src.ingestion.scraper import scrape_article
from src.ingestion.twitter import scrape_twitter_thread
from src.ingestion.youtube import extract_subtitles
from src.ingestion.embedder import get_embedder
from src.synthesis.domain_tagger import DomainTagger
from src.utils.translator import UniversalTranslator

class SourceType(Enum):
    YOUTUBE = "youtube"
    X_TWITTER = "x_twitter"
    INSTAGRAM = "instagram"
    SUBSTACK = "substack"
    ARTICLE = "article"

class UniversalLinkParser:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.embedder = get_embedder()
        self.tagger = DomainTagger(self.db)
        self.translator = UniversalTranslator()

    @staticmethod
    def get_source_type(url: str) -> SourceType:
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            
            if "youtube.com" in domain or "youtu.be" in domain:
                return SourceType.YOUTUBE
            elif "twitter.com" in domain or "x.com" in domain:
                return SourceType.X_TWITTER
            elif "instagram.com" in domain:
                return SourceType.INSTAGRAM
            elif "substack.com" in domain:
                return SourceType.SUBSTACK
            else:
                return SourceType.ARTICLE
        except Exception:
            return SourceType.ARTICLE

    async def process_url(self, url: str, ingestion_mode: str = 'manual') -> ContentItem:
        source_type = self.get_source_type(url)
        raw_text = ""
        
        # 1. Check if already exists
        existing = (await self.db.execute(select(ContentItem).filter(ContentItem.source_url == url))).scalar_one_or_none()
        if existing:
            print(f"URL already ingested: {url}")
            return existing
            
        # 2. Scrape Text
        if source_type == SourceType.YOUTUBE:
            raw_text = await asyncio.to_thread(extract_subtitles, url)
        elif source_type == SourceType.X_TWITTER:
            raw_text = await scrape_twitter_thread(url)
        elif source_type == SourceType.INSTAGRAM:
            from src.ingestion.instagram import extract_instagram_content
            raw_text = await asyncio.to_thread(extract_instagram_content, url)
        else:
            raw_text = await scrape_article(url)
            
        if not raw_text or len(raw_text) < 50:
            raise ValueError(f"Failed to extract meaningful text from {url}")
            
        # 2.5 Force English Translation
        print(f"Checking language for {url} and translating if necessary...")
        raw_text = await self.translator.force_english(raw_text)
            
        # 3. Embed Text
        embedding = await self.embedder.embed_text(raw_text)
        
        # 4. Tag Domains
        domain_tags = await self.tagger.tag_content(
            content_embedding=embedding,
            raw_text=raw_text,
            limit=3,
            threshold_distance=0.60
        )
        
        # 5. Save to Database
        item = ContentItem(
            source_url=url,
            source_type=source_type.value,
            raw_content=raw_text,
            embedding=embedding,
            domain_tags=domain_tags,
            ingestion_mode=ingestion_mode
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        
        print(f"Success: {url} -> {domain_tags}")
        return item
