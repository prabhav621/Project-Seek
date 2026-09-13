from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID

class ContentItemBase(BaseModel):
    source_url: str
    source_type: str
    title: Optional[str] = None
    author: Optional[str] = None
    ingestion_mode: str
    media_type: str = 'text'
    media_url: Optional[str] = None
    transcript_source: Optional[str] = None
    audio_duration_secs: Optional[int] = None
    extraction_status: str = 'pending'
    processed: bool = False

class ContentItemCreate(ContentItemBase):
    raw_text: Optional[str] = None

class ContentItemResponse(ContentItemBase):
    id: UUID
    ingested_at: datetime

    class Config:
        from_attributes = True

class DailyItemBase(BaseModel):
    content_id: Optional[UUID] = None
    item_type: str
    title: Optional[str] = None
    context: Optional[str] = None
    crisis: Optional[str] = None
    architecture: Optional[str] = None
    kata_question: Optional[str] = None
    mirror_question: Optional[str] = None
    quote_text: Optional[str] = None
    quote_author: Optional[str] = None
    quote_context: Optional[str] = None
    inversion_prompt: Optional[str] = None
    suggestion_url: Optional[str] = None
    suggestion_hook: Optional[str] = None
    domains: Optional[List[str]] = None
    difficulty: Optional[str] = None
    forge_date: Optional[date] = None

class DailyItemCreate(DailyItemBase):
    pass

class DailyItemResponse(DailyItemBase):
    id: UUID
    delivered_at: Optional[datetime] = None
    founder_response: Optional[str] = None
    engagement: str
    reply_analysis: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class InterestVectorBase(BaseModel):
    domain: str
    weight: float = 0.5
    momentum: float = 0.0
    decay_rate: float = 0.02
    is_blind_spot: bool = False
    is_graveyard: bool = False

class InterestVectorResponse(InterestVectorBase):
    id: UUID
    last_engaged: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
