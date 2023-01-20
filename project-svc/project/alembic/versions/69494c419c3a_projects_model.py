"""
Projects model

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
        "projects",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("project_id"),
    )

    op.create_table(
        "collaborators",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "email"),
    )

    op.create_table(
        "areas",
        sa.Column("area_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("area_id"),
        sa.PrimaryKeyConstraint("area_id", "project_id"),
    )


def downgrade():
    op.drop_table("collaborators")
    op.drop_table("areas")
    op.drop_table("projects")
