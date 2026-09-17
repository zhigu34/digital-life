"""Add richer details and completion date to shows."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shows", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("shows", sa.Column("release_year", sa.Integer(), nullable=True))
    op.add_column("shows", sa.Column("completed_on", sa.Date(), nullable=True))


def downgrade():
    for column in ("completed_on", "release_year", "source_url"):
        op.drop_column("shows", column)
