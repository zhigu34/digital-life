"""Add optional TMDB-style metadata columns to shows."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shows", sa.Column("source", sa.String(16), nullable=True))
    op.add_column("shows", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("shows", sa.Column("poster_path", sa.Text(), nullable=True))
    op.add_column("shows", sa.Column("seasons", sa.Integer(), nullable=True))
    op.add_column("shows", sa.Column("air_status", sa.String(16), nullable=True))


def downgrade():
    for column in ("air_status", "seasons", "poster_path", "source_id", "source"):
        op.drop_column("shows", column)
