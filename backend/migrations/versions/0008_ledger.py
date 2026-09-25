"""Add the ledger domain: accounts, categories, payees and entries."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("opening_balance_cents", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ledger_accounts_user_id", "ledger_accounts", ["user_id"])

    op.create_table(
        "ledger_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "kind", "name", name="uq_ledger_categories_user_kind_name"),
    )
    op.create_index("ix_ledger_categories_user_id", "ledger_categories", ["user_id"])

    op.create_table(
        "ledger_payees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(40), nullable=False),
        # Case- and whitespace-folded name; the uniqueness rule compares this.
        sa.Column("name_key", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "name_key", name="uq_ledger_payees_user_name"),
    )
    op.create_index("ix_ledger_payees_user_id", "ledger_payees", ["user_id"])

    # Recurring bills may point at a default account/category/payee so that
    # confirming a payment can post a matching entry. Existing rows stay NULL and
    # keep the previous behaviour.
    #
    # These three columns carry no REFERENCES clause: SQLite cannot ALTER TABLE
    # ADD COLUMN with a foreign key (Alembic would have to rebuild the table, and
    # a rebuild of `expenses` re-creates its unnamed FK constraints, which the
    # SQLite dialect rejects). Ownership of the referenced rows is enforced by
    # the ledger endpoints, which answer 409 instead of cascade-deleting. The FK
    # that matters for data lifetime, ledger_entries.expense_id, lives on the new
    # table where CREATE TABLE can declare it with ON DELETE SET NULL.
    op.add_column("expenses", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("expenses", sa.Column("category_id", sa.Integer(), nullable=True))
    op.add_column("expenses", sa.Column("payee_id", sa.Integer(), nullable=True))

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("ledger_accounts.id"), nullable=True),
        sa.Column(
            "from_account_id", sa.Integer(), sa.ForeignKey("ledger_accounts.id"), nullable=True
        ),
        sa.Column(
            "to_account_id", sa.Integer(), sa.ForeignKey("ledger_accounts.id"), nullable=True
        ),
        sa.Column(
            "category_id", sa.Integer(), sa.ForeignKey("ledger_categories.id"), nullable=True
        ),
        sa.Column("payee_id", sa.Integer(), sa.ForeignKey("ledger_payees.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "expense_id",
            sa.Integer(),
            sa.ForeignKey("expenses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ledger_entries_user_id", "ledger_entries", ["user_id"])
    op.create_index("ix_ledger_entries_user_occurred", "ledger_entries", ["user_id", "occurred_on"])
    op.create_index("ix_ledger_entries_expense_id", "ledger_entries", ["expense_id"])


def downgrade():
    op.drop_table("ledger_entries")
    for column in ("payee_id", "category_id", "account_id"):
        op.drop_column("expenses", column)
    op.drop_table("ledger_payees")
    op.drop_table("ledger_categories")
    op.drop_table("ledger_accounts")
