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

SCHEMA_REVISION = "0006"


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
                for constraint in table.constraints:
                    if isinstance(constraint, UniqueConstraint):
                        if tuple(constraint.columns.keys()) not in unique_keys:
                            raise ValueError(f"Backup unique constraint missing in table {name}")
    except sqlite3.DatabaseError as error:
        raise ValueError("Backup is not a valid Digital Life SQLite database") from error


def _staged_snapshot(source: Path, destination_dir: Path) -> Path:
    if not source.is_file():
        raise ValueError("Input database does not exist")
    destination_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".digital-life-", suffix=".db", dir=destination_dir)
    os.close(fd)
    staged = Path(name)
    try:
        with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as original:
            with sqlite3.connect(staged) as target:
                original.backup(target)
                # Produce a standalone snapshot without a companion WAL.
                target.execute("PRAGMA journal_mode=DELETE")
                if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup failed SQLite integrity check")
                if target.execute("PRAGMA foreign_key_check").fetchall():
                    raise ValueError("Backup contains broken foreign keys")
        return staged
    except Exception:
        staged.unlink(missing_ok=True)
        raise


def _sync_file(path):
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def backup(settings: Settings, output: str | Path):
    destination = Path(output).resolve()
    if destination == settings.database_path.resolve():
        raise ValueError("Backup output must differ from the live database")
    staged = _staged_snapshot(settings.database_path, destination.parent)
    try:
        _sync_file(staged)
        os.replace(staged, destination)
    finally:
        staged.unlink(missing_ok=True)


def restore(settings: Settings, source: str | Path):
    source = Path(source).resolve()
    if source == settings.database_path.resolve():
        raise ValueError("Restore input must differ from the live database")
    staged = _staged_snapshot(source, settings.data_dir)
    try:
        validate_database(staged)
        # The operator must stop all backend processes before invoking restore.
        # Never carry pre-backup authentication sessions back into service.
        with sqlite3.connect(staged) as db:
            db.execute("DELETE FROM sessions")
        _sync_file(staged)
        for suffix in ("-wal", "-shm"):
            Path(str(settings.database_path) + suffix).unlink(missing_ok=True)
        os.replace(staged, settings.database_path)
        settings.database_path.chmod(0o600)
    finally:
        staged.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Digital Life operator commands")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Apply pending database migrations")
    admin = commands.add_parser(
        "create-admin", help="Create an administrator; no defaults are seeded"
    )
    admin.add_argument("--username", required=True)
    backup_cmd = commands.add_parser("backup", help="Take a consistent SQLite online backup")
    backup_cmd.add_argument("--output", required=True)
    restore_cmd = commands.add_parser("restore", help="Restore a backup, with backend stopped")
    restore_cmd.add_argument("--input", required=True)
    commands.add_parser("pending-migration", help="Exit 1 when database migrations are pending")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if args.command == "migrate":
            migrate(settings)
        elif args.command == "create-admin":
            password = os.getenv("DIGITAL_LIFE_ADMIN_PASSWORD") or getpass.getpass(
                "Admin password: "
            )
            create_admin(settings, args.username, password)
        elif args.command == "backup":
            backup(settings, args.output)
        elif args.command == "pending-migration":
            if migration_pending(settings):
                print("pending")
                parser.exit(1)
            print("up-to-date")
        else:
            restore(settings, args.input)
    except ValidationError:
        parser.exit(
            1, "Invalid account: username 3–32 permitted characters; password 12–128 chars.\n"
        )
    except (ValueError, OSError, sqlite3.DatabaseError) as error:
        parser.exit(1, f"Operation failed: {error}\n")
    print(f"{args.command}: complete")


if __name__ == "__main__":
    main()
