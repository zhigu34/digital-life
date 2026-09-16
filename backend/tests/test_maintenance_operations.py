import sqlite3

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from test_auth import PASSWORD, sign_in
from test_maintenance import create_item

from app.cli import backup, restore
from app.config import Settings
from app.database import ROOT, make_engine, migrate, session_factory
from app.main import create_app
from app.models import Task, User
from app.security import hash_password


def test_migrate_0001_database_keeps_old_accounts_and_records(tmp_path):
    from datetime import datetime

    settings = Settings(tmp_path / "legacy")
    engine = make_engine(settings)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
    with session_factory(engine)() as db:
        user = User(
            username="admin",
            display_name="原账号",
            is_admin=True,
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()
        db.add(Task(user_id=user.id, title="迁移前待办", created_at=datetime(2024, 1, 1)))
        db.commit()
    old_backup = tmp_path / "before-upgrade.db"
    backup(settings, old_backup)
    with sqlite3.connect(old_backup) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001",)
    migrate(settings)
    migrate(settings)
    engine.dispose()
    with TestClient(create_app(settings.data_dir)) as client:
        csrf = sign_in(client)
        assert client.get("/api/tasks").json()[0]["title"] == "迁移前待办"
        assert client.get("/api/auth/session").json()["user"]["display_name"] == "原账号"
        assert client.get("/api/maintenance").json() == []
        create_item(client, csrf)
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0006",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    # Old snapshots stay usable with their matching version, not silently restored into v3.
    with pytest.raises(ValueError):
        restore(Settings(tmp_path / "wrong-version"), old_backup)


def test_backup_restore_preserves_maintenance_and_corrected_history(accounts, tmp_path):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    path = f"/api/maintenance/{item['id']}"
    alice.post(
        path + "/complete",
        headers=ah,
        json={"completed_on": "2024-02-29", "cost_cents": 1800, "notes": "更换"},
    )
    recent = alice.get(path + "/history").json()[0]
    alice.patch(path + f"/history/{recent['id']}", headers=ah, json={"completed_on": "2024-02-28"})
    before = alice.get("/api/export").json()
    destination = tmp_path / "saved.db"
    backup(app.state.settings, destination)
    settings = Settings(tmp_path / "restored")
    restore(settings, destination)
    with TestClient(create_app(settings.data_dir)) as client:
        sign_in(client, "alice")
        after = client.get("/api/export").json()
        assert after["maintenance"] == before["maintenance"]
        assert after["maintenance_logs"] == before["maintenance_logs"]
        assert after["maintenance"][0]["next_due"] == "2024-03-28"
        assert client.get(path + "/history").json()[0]["cost_cents"] == 1800
        sign_in(client, "bob")
        assert client.get("/api/maintenance").json() == []


@pytest.mark.parametrize(
    "corruption", ["broken_parent", "missing_parent_fk", "missing_unique", "partial_unique"]
)
def test_restore_rejects_bad_maintenance_relationships(accounts, tmp_path, corruption):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    destination = tmp_path / "bad.db"
    backup(app.state.settings, destination)
    with sqlite3.connect(destination) as db:
        if corruption == "broken_parent":
            db.execute("UPDATE maintenance_logs SET maintenance_id = 999999")
        else:
            db.execute("ALTER TABLE maintenance_logs RENAME TO old_logs")
            foreign_key = "FOREIGN KEY(maintenance_id) REFERENCES maintenance(id) ON DELETE CASCADE"
            constraints = ["UNIQUE(maintenance_id, completed_on)"]
            if corruption == "missing_parent_fk":
                pass
            else:
                constraints = [foreign_key]
            sql = (
                """CREATE TABLE maintenance_logs (
                id INTEGER NOT NULL PRIMARY KEY,
                maintenance_id INTEGER NOT NULL,
                completed_on DATE NOT NULL,
                notes TEXT NOT NULL,
                cost_cents INTEGER,
                currency VARCHAR(3) NOT NULL,
                created_at DATETIME NOT NULL, """
                + ", ".join(constraints)
                + ")"
            )
            db.execute(sql)
            db.execute("INSERT INTO maintenance_logs SELECT * FROM old_logs")
            db.execute("DROP TABLE old_logs")
            if corruption == "partial_unique":
                db.execute(
                    "CREATE UNIQUE INDEX partial_log_date "
                    "ON maintenance_logs(maintenance_id, completed_on) "
                    "WHERE cost_cents IS NOT NULL"
                )
    with pytest.raises(ValueError):
        restore(app.state.settings, destination)
    assert alice.get(f"/api/maintenance/{item['id']}/history").status_code == 200
