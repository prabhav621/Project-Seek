"""Add vector and b-tree indexes

Revision ID: f7d1b32a9000
Revises: ea5d3e74da87
Create Date: 2026-09-18 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7d1b32a9000'
down_revision: Union[str, None] = 'ea5d3e74da87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # C2 — Add HNSW Vector Indexes
    op.execute("CREATE INDEX idx_content_items_embedding ON content_items USING hnsw (embedding vector_cosine_ops);")
    op.execute("CREATE INDEX idx_daily_items_embedding ON daily_items USING hnsw (embedding vector_cosine_ops);")
    op.execute("CREATE INDEX idx_interest_vectors_embedding ON interest_vectors USING hnsw (embedding vector_cosine_ops);")

    # I4 — Add B-Tree Indexes
    op.create_index('idx_daily_items_content_id', 'daily_items', ['content_id'])
    op.create_index('idx_daily_items_forge_date', 'daily_items', ['forge_date'])

def downgrade() -> None:
    # Drop B-Tree Indexes
    op.drop_index('idx_daily_items_forge_date', table_name='daily_items')
    op.drop_index('idx_daily_items_content_id', table_name='daily_items')

    # Drop HNSW Vector Indexes
    op.execute("DROP INDEX IF EXISTS idx_interest_vectors_embedding;")
    op.execute("DROP INDEX IF EXISTS idx_daily_items_embedding;")
    op.execute("DROP INDEX IF EXISTS idx_content_items_embedding;")
