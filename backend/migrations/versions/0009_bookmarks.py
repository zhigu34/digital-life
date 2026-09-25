"""Add the bookmarks domain: saved web links grouped by folder."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bookmarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("folder", sa.String(60), nullable=True),
        sa.Column("starred", sa.Boolean(), nullable=False),
        sa.Column("visit_count", sa.Integer(), nullable=False),
        sa.Column("last_visited_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bookmarks_user_id", "bookmarks", ["user_id"])
    op.create_index("ix_bookmarks_user_folder", "bookmarks", ["user_id", "folder"])


def downgrade():
    op.drop_index("ix_bookmarks_user_folder", table_name="bookmarks")
    op.drop_index("ix_bookmarks_user_id", table_name="bookmarks")
    op.drop_table("bookmarks")
