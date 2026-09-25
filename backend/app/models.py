from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(60))
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Shanghai")
    theme: Mapped[str] = mapped_column(String(10), default="light")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(Integer, index=True)


class Owned:
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Task(Owned, Base):
    __tablename__ = "tasks"
    title: Mapped[str] = mapped_column(String(160))
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="todo")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Expense(Owned, Base):
    __tablename__ = "expenses"
    title: Mapped[str] = mapped_column(String(120))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    period_months: Mapped[int] = mapped_column(Integer, default=1)
    next_due: Mapped[date] = mapped_column(Date)
    anchor_day: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    # Optional ledger defaults for "confirm paid". Plain integers rather than
    # ForeignKey columns: SQLite rejects ALTER TABLE ADD COLUMN with a foreign
    # key, and ownership is checked by the ledger endpoints (409, never a
    # cascade delete). See migration 0008.
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Show(Owned, Base):
    __tablename__ = "shows"
    title: Mapped[str] = mapped_column(String(160))
    media_type: Mapped[str] = mapped_column(String(10), default="tv")
    status: Mapped[str] = mapped_column(String(10), default="planned")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    update_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    seasons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    air_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class Milestone(Owned, Base):
    __tablename__ = "milestones"
    title: Mapped[str] = mapped_column(String(120))
    date: Mapped[date] = mapped_column(Date)
    repeats_yearly: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class Note(Owned, Base):
    __tablename__ = "notes"
    content: Mapped[str] = mapped_column(Text)
    entry_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class CheckIn(Owned, Base):
    __tablename__ = "checkins"
    title: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Project(Owned, Base):
    __tablename__ = "projects"
    title: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class CheckInLog(Base):
    __tablename__ = "checkin_logs"
    __table_args__ = (UniqueConstraint("checkin_id", "checked_on", name="uq_checkin_logs_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    checkin_id: Mapped[int] = mapped_column(
        ForeignKey("checkins.id", ondelete="CASCADE"),
        index=True,
    )
    checked_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Maintenance(Owned, Base):
    __tablename__ = "maintenance"
    title: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    period_value: Mapped[int] = mapped_column(Integer)
    period_unit: Mapped[str] = mapped_column(String(6))
    remind_days: Mapped[int] = mapped_column(Integer, default=7)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_completed: Mapped[date] = mapped_column(Date)
    next_due: Mapped[date] = mapped_column(Date)


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"
    __table_args__ = (
        UniqueConstraint("maintenance_id", "completed_on", name="uq_maintenance_logs_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    maintenance_id: Mapped[int] = mapped_column(
        ForeignKey("maintenance.id", ondelete="CASCADE"),
        index=True,
    )
    completed_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LedgerAccount(Owned, Base):
    __tablename__ = "ledger_accounts"
    name: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10), default="debit")
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    # Negative opening balances are legitimate: a credit card starts in debt.
    opening_balance_cents: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LedgerCategory(Owned, Base):
    __tablename__ = "ledger_categories"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "name", name="uq_ledger_categories_user_kind_name"),
    )
    name: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(10))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LedgerPayee(Owned, Base):
    __tablename__ = "ledger_payees"
    __table_args__ = (UniqueConstraint("user_id", "name_key", name="uq_ledger_payees_user_name"),)
    name: Mapped[str] = mapped_column(String(40))
    # Case- and whitespace-folded name; uniqueness is enforced on this column.
    name_key: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10), default="merchant")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class LedgerEntry(Owned, Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (Index("ix_ledger_entries_user_occurred", "user_id", "occurred_on"),)
    occurred_on: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(10))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    account_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_accounts.id"), nullable=True)
    from_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("ledger_accounts.id"), nullable=True
    )
    to_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("ledger_accounts.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("ledger_categories.id"), nullable=True
    )
    payee_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_payees.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    # Set when a recurring bill generated this entry; deleting the bill keeps the entry.
    expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime)
