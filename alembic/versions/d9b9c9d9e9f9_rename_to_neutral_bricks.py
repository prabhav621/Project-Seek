"""Rename strategy_library to neutral_bricks

Revision ID: d9b9c9d9e9f9
Revises: c8a84c867dc3
Create Date: 2026-10-06 12:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd9b9c9d9e9f9'
down_revision: Union[str, None] = 'c8a84c867dc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename the table
    op.rename_table('strategy_library', 'neutral_bricks')
    
    # Drop old indexes
    op.drop_index('ix_strategy_library_source_content_id', table_name='neutral_bricks')
    op.drop_index('ix_strategy_library_master_strategy_id', table_name='neutral_bricks')

    # Drop old columns
    op.drop_column('neutral_bricks', 'master_strategy_id')
    op.drop_column('neutral_bricks', 'lens_used')
    op.drop_column('neutral_bricks', 'strategy_name')
    op.drop_column('neutral_bricks', 'core_concept')
    op.drop_column('neutral_bricks', 'why_it_works')
    op.drop_column('neutral_bricks', 'failure_modes')
    op.drop_column('neutral_bricks', 'implementation_challenge')
    
    # Add new columns
    op.add_column('neutral_bricks', sa.Column('core_thesis', sa.Text(), nullable=True))
    op.add_column('neutral_bricks', sa.Column('key_mechanics', sa.Text(), nullable=True))
    op.add_column('neutral_bricks', sa.Column('critical_pointers', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('neutral_bricks', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))

    # Add new index
    op.create_index(op.f('ix_neutral_bricks_source_content_id'), 'neutral_bricks', ['source_content_id'], unique=False)
    
    # Rename foreign key constraint for source_content_id
    op.drop_constraint('strategy_library_source_content_id_fkey', 'neutral_bricks', type_='foreignkey')
    op.create_foreign_key('neutral_bricks_source_content_id_fkey', 'neutral_bricks', 'content_items', ['source_content_id'], ['id'])

    # Update influence_log if it exists
    conn = op.get_bind()
    from sqlalchemy.engine import reflection
    insp = reflection.Inspector.from_engine(conn)
    if 'influence_log' in insp.get_table_names():
        # Drop old FK
        op.drop_constraint('influence_log_strategy_id_fkey', 'influence_log', type_='foreignkey')
        
        # Rename column
        op.alter_column('influence_log', 'strategy_id', new_column_name='brick_id')
        
        # Recreate FK
        op.create_foreign_key('influence_log_brick_id_fkey', 'influence_log', 'neutral_bricks', ['brick_id'], ['id'])
    else:
        # Create influence_log since it was missing
        op.create_table(
            'influence_log',
            sa.Column('id', sa.UUID(), primary_key=True),
            sa.Column('brick_id', sa.UUID(), sa.ForeignKey('neutral_bricks.id'), index=True),
            sa.Column('decision_made', sa.Text()),
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now())
        )


def downgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy.engine import reflection
    insp = reflection.Inspector.from_engine(conn)
    
    # Downgrade influence_log
    if 'influence_log' in insp.get_table_names():
        op.drop_constraint('influence_log_brick_id_fkey', 'influence_log', type_='foreignkey')
        op.alter_column('influence_log', 'brick_id', new_column_name='strategy_id')
        op.create_foreign_key('influence_log_strategy_id_fkey', 'influence_log', 'neutral_bricks', ['strategy_id'], ['id'])

    # Revert neutral_bricks constraints and indexes
    op.drop_constraint('neutral_bricks_source_content_id_fkey', 'neutral_bricks', type_='foreignkey')
    op.create_foreign_key('strategy_library_source_content_id_fkey', 'neutral_bricks', 'content_items', ['source_content_id'], ['id'])
    op.drop_index(op.f('ix_neutral_bricks_source_content_id'), table_name='neutral_bricks')

    # Drop new columns
    op.drop_column('neutral_bricks', 'updated_at')
    op.drop_column('neutral_bricks', 'critical_pointers')
    op.drop_column('neutral_bricks', 'key_mechanics')
    op.drop_column('neutral_bricks', 'core_thesis')

    # Re-add old columns
    op.add_column('neutral_bricks', sa.Column('implementation_challenge', sa.Text(), nullable=True))
    op.add_column('neutral_bricks', sa.Column('failure_modes', sa.Text(), nullable=True))
    op.add_column('neutral_bricks', sa.Column('why_it_works', sa.Text(), nullable=True))
    op.add_column('neutral_bricks', sa.Column('core_concept', sa.Text(), nullable=True))
    op.add_column('neutral_bricks', sa.Column('strategy_name', sa.Text(), nullable=True))
    op.add_column('neutral_bricks', sa.Column('lens_used', sa.Text(), nullable=True))
    op.add_column('neutral_bricks', sa.Column('master_strategy_id', sa.UUID(), nullable=True))

    # Re-add old indexes
    op.create_index('ix_strategy_library_master_strategy_id', 'neutral_bricks', ['master_strategy_id'], unique=False)
    op.create_index('ix_strategy_library_source_content_id', 'neutral_bricks', ['source_content_id'], unique=False)

    # Rename table back
    op.rename_table('neutral_bricks', 'strategy_library')
