"""Add Strategy Bricks tables

Revision ID: c8a84c867dc3
Revises: f7d1b32a9000
Create Date: 2026-10-06 15:29:24.996957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a84c867dc3'
down_revision: Union[str, None] = 'f7d1b32a9000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import pgvector

def upgrade() -> None:
    # Add strategy_status to content_items
    op.add_column('content_items', sa.Column('strategy_status', sa.Text(), server_default='pending'))
    
    # Add check constraint for strategy_status
    op.create_check_constraint(
        'content_items_strategy_status_check',
        'content_items',
        "strategy_status IN ('pending', 'processing', 'completed', 'skipped', 'failed')"
    )

    # Create strategy_library table
    op.create_table(
        'strategy_library',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('source_content_id', sa.UUID(), sa.ForeignKey('content_items.id')),
        sa.Column('master_strategy_id', sa.UUID(), sa.ForeignKey('strategy_library.id'), nullable=True),
        sa.Column('lens_used', sa.Text()),
        sa.Column('strategy_name', sa.Text()),
        sa.Column('core_concept', sa.Text()),
        sa.Column('why_it_works', sa.Text()),
        sa.Column('failure_modes', sa.Text()),
        sa.Column('implementation_challenge', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=768))
    )
    
    # Add indexes for strategy_library to avoid full table scans
    op.create_index(op.f('ix_strategy_library_source_content_id'), 'strategy_library', ['source_content_id'], unique=False)
    op.create_index(op.f('ix_strategy_library_master_strategy_id'), 'strategy_library', ['master_strategy_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_strategy_library_master_strategy_id'), table_name='strategy_library')
    op.drop_index(op.f('ix_strategy_library_source_content_id'), table_name='strategy_library')
    op.drop_table('strategy_library')
    op.drop_constraint('content_items_strategy_status_check', 'content_items', type_='check')
    op.drop_column('content_items', 'strategy_status')
