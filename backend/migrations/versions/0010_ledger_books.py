"""Add ledger books: a label that scopes entries and bills."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

DEFAULT_BOOK_NAME = "日常"


def upgrade():
    op.create_table(
        "ledger_books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_ledger_books_user_name"),
    )
    op.create_index("ix_ledger_books_user_id", "ledger_books", ["user_id"])

    # Both columns join an existing table, so neither can declare REFERENCES:
    # SQLite cannot ALTER TABLE ADD COLUMN with a foreign key. Ownership of the
    # referenced book is enforced by the ledger endpoints, which answer 409
    # instead of cascade-deleting. Migration 0008 carries the same reasoning.
    op.add_column("expenses", sa.Column("book_id", sa.Integer(), nullable=True))
    op.add_column("ledger_entries", sa.Column("book_id", sa.Integer(), nullable=True))
    op.create_index("ix_ledger_entries_book_id", "ledger_entries", ["book_id"])

    # Everything already recorded predates books. Left unlabelled it would read
    # as data loss, so each user gets a "日常" book and their existing bills and
    # entries are filed under it.
    connection = op.get_bind()
    created = datetime.now(UTC).replace(tzinfo=None)
    statements = (
        "UPDATE ledger_entries SET book_id = :book_id WHERE user_id = :user_id",
        "UPDATE expenses SET book_id = :book_id WHERE user_id = :user_id",
    )
    for (user_id,) in connection.execute(sa.text("SELECT id FROM users")).fetchall():
        result = connection.execute(
            sa.text(
                "INSERT INTO ledger_books (user_id, name, archived, sort_order, created_at) "
                "VALUES (:user_id, :name, 0, 0, :created_at)"
            ),
            {"user_id": user_id, "name": DEFAULT_BOOK_NAME, "created_at": created},
        )
        for statement in statements:
            connection.execute(
                sa.text(statement), {"book_id": result.lastrowid, "user_id": user_id}
            )


def downgrade():
    op.drop_index("ix_ledger_entries_book_id", "ledger_entries")
    op.drop_column("ledger_entries", "book_id")
    op.drop_column("expenses", "book_id")
    op.drop_table("ledger_books")
