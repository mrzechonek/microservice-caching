"""
Node model

Revision ID: 0488490ec66b
Revises:
Create Date: 2023-01-11 12:11:46.523428

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0488490ec66b"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nodes",
        sa.Column("node_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("tags", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("node_id"),
    )

    pass


def downgrade():
    pass
