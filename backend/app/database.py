from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def make_engine(settings: Settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    engine = create_engine(
        "sqlite:///" + str(settings.database_path),
        connect_args={"check_same_thread": False, "timeout": 15},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA journal_mode=WAL")

    return engine


def migrate(settings: Settings):
    engine = make_engine(settings)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    try:
        with engine.connect() as connection:
            # Serialize migration checks across processes starting together.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
    finally:
        engine.dispose()
    settings.database_path.chmod(0o600)


def migration_pending(settings: Settings) -> bool:
    """True when the database revision differs from the migration head."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(ROOT / "migrations"))
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
    return current != script.get_current_head()


def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            # Read-modify-write operations (pay/advance/revoke) must be atomic.
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        yield session
