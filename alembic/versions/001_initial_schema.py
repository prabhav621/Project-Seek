"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-09-12 16:04:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # We must ensure the vector extension is created
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    op.create_table('content_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('source_type', sa.Text(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('ingestion_mode', sa.Text(), nullable=False),
        sa.Column('media_type', sa.Text(), server_default='text', nullable=True),
        sa.Column('media_url', sa.Text(), nullable=True),
        sa.Column('transcript_source', sa.Text(), nullable=True),
        sa.Column('audio_duration_secs', sa.Integer(), nullable=True),
        sa.Column('extraction_status', sa.Text(), server_default='pending', nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=768), nullable=True),
        sa.Column('processed', sa.Boolean(), server_default='false', nullable=True),
        sa.CheckConstraint("extraction_status IN ('pending', 'processing', 'completed', 'failed', 'retry')", name='content_items_extraction_status_check'),
        sa.CheckConstraint("ingestion_mode IN ('manual', 'auto', 'genesis')", name='content_items_ingestion_mode_check'),
        sa.CheckConstraint("media_type IN ('text', 'video', 'audio', 'mixed')", name='content_items_media_type_check'),
        sa.CheckConstraint("source_type IN ('youtube', 'x_twitter', 'instagram', 'substack', 'article', 'other')", name='content_items_source_type_check'),
        sa.CheckConstraint("transcript_source IN ('subtitles', 'gemini_audio', 'whisper', 'crawl4ai', 'manual')", name='content_items_transcript_source_check'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('interest_vectors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('domain', sa.Text(), nullable=False),
        sa.Column('weight', sa.Float(), server_default='0.5', nullable=True),
        sa.Column('momentum', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('decay_rate', sa.Float(), server_default='0.02', nullable=True),
        sa.Column('last_engaged', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_blind_spot', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('is_graveyard', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('weight >= 0.0 AND weight <= 1.0', name='interest_vectors_weight_check'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain')
    )
    
    op.create_table('daily_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_type', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('crisis', sa.Text(), nullable=True),
        sa.Column('architecture', sa.Text(), nullable=True),
        sa.Column('kata_question', sa.Text(), nullable=True),
        sa.Column('mirror_question', sa.Text(), nullable=True),
        sa.Column('quote_text', sa.Text(), nullable=True),
        sa.Column('quote_author', sa.Text(), nullable=True),
        sa.Column('quote_context', sa.Text(), nullable=True),
        sa.Column('inversion_prompt', sa.Text(), nullable=True),
        sa.Column('suggestion_url', sa.Text(), nullable=True),
        sa.Column('suggestion_hook', sa.Text(), nullable=True),
        sa.Column('domains', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('difficulty', sa.Text(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('forge_date', sa.Date(), nullable=True),
        sa.Column('founder_response', sa.Text(), nullable=True),
        sa.Column('engagement', sa.Text(), server_default='pending', nullable=True),
        sa.Column('reply_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=768), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("difficulty IN ('intro', 'deep')", name='daily_items_difficulty_check'),
        sa.CheckConstraint("engagement IN ('pending', 'skipped', 'read', 'responded', 'debated')", name='daily_items_engagement_check'),
        sa.CheckConstraint("item_type IN ('deep_kata', 'quick_kata', 'aphorism', 'inversion_prompt', 'curated_suggestion')", name='daily_items_item_type_check'),
        sa.ForeignKeyConstraint(['content_id'], ['content_items.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('daily_items')
    op.drop_table('interest_vectors')
    op.drop_table('content_items')
