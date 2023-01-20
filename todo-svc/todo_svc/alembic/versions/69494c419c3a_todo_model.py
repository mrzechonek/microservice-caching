"""
Todo List model

Revision ID: 69494c419c3a
Revises: -
Create Date: 2023-01-02 13:13:06.268387

"""
import sqlalchemy as sa
from alembic import op

revision = "69494c419c3a"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lists",
        sa.Column("list_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("list_id"),
    )

    op.create_table(
        "collaborators",
        sa.Column("list_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["lists.list_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("list_id", "email"),
    )

    op.create_table(
        "entries",
        sa.Column("entry_id", sa.Text(), nullable=False),
        sa.Column("list_id", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["list_id"], ["lists.list_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("entry_id"),
        sa.PrimaryKeyConstraint("entry_id", "list_id"),
    )


def downgrade():
    op.drop_table("collaborators")
    op.drop_table("entries")
    op.drop_table("lists")
