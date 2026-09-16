"""Operator commands. Restore requires all backend processes to be stopped."""

import argparse
import getpass
import os
import sqlite3
import tempfile
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import UniqueConstraint, select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.database import make_engine, migrate, migration_pending, session_factory
from app.models import Base, User
from app.schemas import UserCreate
from app.security import hash_password

SCHEMA_REVISION = "0007"


def create_admin(settings: Settings, username: str, password: str):
    payload = UserCreate(username=username, password=password, display_name=username)
    migrate(settings)
    engine = make_engine(settings)
    try:
        with session_factory(engine)() as db:
            if db.scalar(select(User.id).where(User.username == payload.username)) is not None:
                raise ValueError("Username already exists; refusing to overwrite account")
            db.add(
                User(
                    username=payload.username,
                    display_name=payload.display_name,
                    password_hash=hash_password(payload.password),
                    is_admin=True,
                )
            )
            try:
                db.commit()
            except IntegrityError:
                raise ValueError("Username already exists") from None
    finally:
        engine.dispose()


def validate_database(path: Path):
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            db.execute("PRAGMA trusted_schema=OFF")
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("Backup failed SQLite integrity check")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Backup contains broken foreign keys")
            expected_tables = set(Base.metadata.tables) | {"alembic_version"}
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if tables != expected_tables:
                raise ValueError("Backup schema does not match this application version")
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type IN ('trigger', 'view')"
            ).fetchone():
                raise ValueError("Unexpected executable schema objects in backup")
            if db.execute("SELECT version_num FROM alembic_version").fetchall() != [
                (SCHEMA_REVISION,)
            ]:
                raise ValueError("Backup migration version does not match this application version")
            for name, table in Base.metadata.tables.items():
                actual = {row[1]: row for row in db.execute(f'PRAGMA table_info("{name}")')}
                if set(actual) != set(table.columns.keys()):
                    raise ValueError(f"Backup columns do not match table {name}")
                for column in table.columns:
                    row = actual[column.name]
                    if row[2].upper() != str(column.type).upper():
                        raise ValueError(f"Backup column type does not match table {name}")
                    if bool(row[3]) != (not column.nullable) or bool(row[5]) != column.primary_key:
                        raise ValueError(f"Backup column constraints do not match table {name}")
                foreign_keys = db.execute(f'PRAGMA foreign_key_list("{name}")').fetchall()
                actual_fks = {(row[3], row[2], row[4], row[6]) for row in foreign_keys}
                expected_fks = {
                    (fk.parent.name, fk.column.table.name, fk.column.name, fk.ondelete)
                    for fk in table.foreign_keys
                }
                if actual_fks != expected_fks:
                    raise ValueError(f"Backup ownership constraint missing in table {name}")
                unique_keys = set()
                for index in db.execute(f'PRAGMA index_list("{name}")').fetchall():
                    # A partial unique index only applies to rows matching its
                    # WHERE clause, so it cannot satisfy a table-wide invariant.
                    if index[2] and not index[4]:
                        index_name = index[1].replace('"', '""')
                        unique_keys.add(
                            tuple(
                                row[2] for row in db.execute(f'PRAGMA index_info("{index_name}")')
                            )
                        )
                expected_uniques = {
                    tuple(column.name for column in constraint.columns)
                    for constraint in table.constraints
                    if isinstance(constraint, UniqueConstraint)
                }
                expected_uniques.update(
                    (column.name,) for column in table.columns if column.unique
                )
                if not expected_uniques.issubset(unique_keys):
                    raise ValueError(f"Backup uniqueness constraint missing in table {name}")
    except sqlite3.DatabaseError as exc:
        raise ValueError("Backup is not a valid SQLite database") from exc


def backup(settings: Settings, destination: Path):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    source = settings.database_path
    if not source.exists():
        raise ValueError("Database does not exist")
    with sqlite3.connect(source) as live, sqlite3.connect(destination) as copy:
        live.backup(copy)
    validate_database(destination)


def restore(settings: Settings, source: Path):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        raise ValueError("Backup does not exist")
    fd, staged_name = tempfile.mkstemp(prefix=".digital-life-", suffix=".db", dir=settings.data_dir)
    os.close(fd)
    staged = Path(staged_name)
    try:
        with sqlite3.connect(source) as source_db, sqlite3.connect(staged) as staged_db:
            source_db.backup(staged_db)
        validate_database(staged)
        with sqlite3.connect(staged) as db:
            db.execute("DELETE FROM sessions")
        os.replace(staged, settings.database_path)
    finally:
        staged.unlink(missing_ok=True)


def migration_status(settings: Settings):
    pending = migration_pending(settings)
    return "pending" if pending else "current"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="digital-life")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    create = sub.add_parser("create-admin")
    create.add_argument("--username", required=True)
    sub.add_parser("migration-status")
    backup_parser = sub.add_parser("backup")
    backup_parser.add_argument("destination", type=Path)
    restore_parser = sub.add_parser("restore")
    restore_parser.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    try:
        if args.command == "migrate":
            migrate(settings)
        elif args.command == "create-admin":
            password = os.getenv("DIGITAL_LIFE_ADMIN_PASSWORD") or getpass.getpass("Password: ")
            create_admin(settings, args.username, password)
        elif args.command == "migration-status":
            print(migration_status(settings))
        elif args.command == "backup":
            backup(settings, args.destination)
        elif args.command == "restore":
            restore(settings, args.source)
    except (ValueError, ValidationError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
