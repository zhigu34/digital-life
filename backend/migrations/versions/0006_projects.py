"""Split ongoing check-ins into an independent projects collection."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    # Existing "ongoing" check-ins become projects; their day logs are not
    # silently destroyed but summarized into the project notes.
    op.execute(
        """
        INSERT INTO projects (user_id, title, notes, status, created_at)
        SELECT c.user_id,
               c.title,
               CASE
                 WHEN COUNT(l.id) = 0 THEN c.notes
                 ELSE (CASE WHEN c.notes = '' THEN '' ELSE c.notes || char(10) END)
                      || '原打卡 ' || COUNT(l.id)
                      || ' 条（' || MIN(l.checked_on) || ' ~ ' || MAX(l.checked_on) || '）'
               END,
               'active',
               c.created_at
        FROM checkins c
        LEFT JOIN checkin_logs l ON l.checkin_id = c.id
        WHERE c.kind = 'ongoing'
        GROUP BY c.id
        """
    )
    # The migration connection does not enable SQLite foreign-key cascades.
    op.execute(
        "DELETE FROM checkin_logs WHERE checkin_id IN "
        "(SELECT id FROM checkins WHERE kind = 'ongoing')"
    )
    op.execute("DELETE FROM checkins WHERE kind = 'ongoing'")


def downgrade():
    op.drop_table("projects")
