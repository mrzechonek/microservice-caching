"""
Node configuration

Revision ID: 920246ccd857
Revises: 0488490ec66b
Create Date: 2023-01-11 21:24:48.373371

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "920246ccd857"
down_revision = "0488490ec66b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nodes", sa.Column("configuration", JSONB(), nullable=False, server_default="{}"))


def downgrade():
    pass
