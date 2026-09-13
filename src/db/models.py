from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, ForeignKey, Text, Date, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class ContentItem(Base):
    __tablename__ = 'content_items'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(Text, nullable=False)
    source_type = Column(Text, nullable=False)
    raw_text = Column(Text)
    title = Column(Text)
    author = Column(Text)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    ingestion_mode = Column(Text, nullable=False)
    media_type = Column(Text, server_default='text')
    media_url = Column(Text)
    transcript_source = Column(Text)
    audio_duration_secs = Column(Integer)
    extraction_status = Column(Text, server_default='pending')
    embedding = Column(Vector(768))
    processed = Column(Boolean, server_default='false')

    daily_items = relationship("DailyItem", back_populates="content_item")

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('youtube', 'x_twitter', 'instagram', 'substack', 'article', 'other')",
            name='content_items_source_type_check'
        ),
        CheckConstraint(
            "ingestion_mode IN ('manual', 'auto', 'genesis')",
            name='content_items_ingestion_mode_check'
        ),
        CheckConstraint(
            "media_type IN ('text', 'video', 'audio', 'mixed')",
            name='content_items_media_type_check'
        ),
        CheckConstraint(
            "transcript_source IN ('subtitles', 'gemini_audio', 'whisper', 'crawl4ai', 'manual')",
            name='content_items_transcript_source_check'
        ),
        CheckConstraint(
            "extraction_status IN ('pending', 'processing', 'completed', 'failed', 'retry')",
            name='content_items_extraction_status_check'
        ),
    )

class DailyItem(Base):
    __tablename__ = 'daily_items'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(UUID(as_uuid=True), ForeignKey('content_items.id'))
    item_type = Column(Text, nullable=False)
    
    # Structured content fields
    title = Column(Text)
    context = Column(Text)
    crisis = Column(Text)
    architecture = Column(Text)
    kata_question = Column(Text)
    mirror_question = Column(Text)
    quote_text = Column(Text)
    quote_author = Column(Text)
    quote_context = Column(Text)
    inversion_prompt = Column(Text)
    suggestion_url = Column(Text)
    suggestion_hook = Column(Text)
    
    # Metadata
    domains = Column(ARRAY(Text))
    difficulty = Column(Text)
    
    # Delivery & engagement tracking
    delivered_at = Column(DateTime(timezone=True))
    forge_date = Column(Date)
    founder_response = Column(Text)
    engagement = Column(Text, server_default='pending')
    
    # Reply analysis
    reply_analysis = Column(JSONB)
    embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    content_item = relationship("ContentItem", back_populates="daily_items")

    __table_args__ = (
        CheckConstraint(
            "item_type IN ('deep_kata', 'quick_kata', 'aphorism', 'inversion_prompt', 'curated_suggestion')",
            name='daily_items_item_type_check'
        ),
        CheckConstraint(
            "difficulty IN ('intro', 'deep')",
            name='daily_items_difficulty_check'
        ),
        CheckConstraint(
            "engagement IN ('pending', 'skipped', 'read', 'responded', 'debated')",
            name='daily_items_engagement_check'
        ),
    )

class InterestVector(Base):
    __tablename__ = 'interest_vectors'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(Text, unique=True, nullable=False)
    weight = Column(Float, server_default='0.5')
    momentum = Column(Float, server_default='0.0')
    decay_rate = Column(Float, server_default='0.02')
    last_engaged = Column(DateTime(timezone=True))
    is_blind_spot = Column(Boolean, server_default='false')
    is_graveyard = Column(Boolean, server_default='false')
    embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "weight >= 0.0 AND weight <= 1.0",
            name='interest_vectors_weight_check'
        ),
    )
