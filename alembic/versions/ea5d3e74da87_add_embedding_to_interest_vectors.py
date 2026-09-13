"""Add embedding to interest_vectors

Revision ID: ea5d3e74da87
Revises: 001
Create Date: 2026-09-13 01:49:49.526761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea5d3e74da87'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import pgvector

def upgrade() -> None:
    op.add_column('interest_vectors', sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=768), nullable=True))


def downgrade() -> None:
    op.drop_column('interest_vectors', 'embedding')
