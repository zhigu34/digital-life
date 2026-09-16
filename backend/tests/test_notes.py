import sqlite3
from datetime import datetime

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from test_auth import PASSWORD, sign_in

from app.cli import backup, restore
from app.config import Settings
from app.database import ROOT, make_engine, migrate, session_factory
from app.main import create_app
from app.models import Task, User
from app.security import hash_password


def test_note_crud_validation_and_export(accounts):
    _, _, _, alice, headers, bob, bob_headers = accounts
    missing_date = alice.post("/api/notes", json={"content": "缺少日期"}, headers=headers)
    assert missing_date.status_code == 422
    assert (
        alice.post(
            "/api/notes",
            json={"content": "x" * 4001, "entry_date": "2026-09-16"},
            headers=headers,
        ).status_code
        == 422
    )
    created = alice.post(
        "/api/notes",
        json={"content": "今天的晚霞很好看", "entry_date": "2026-09-16"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    note = created.json()
    assert note["id"] >= 1 and note["created_at"]
    # CSRF is mandatory and foreign ids stay invisible.
    no_csrf = alice.post("/api/notes", json={"content": "x", "entry_date": "2026-09-16"})
    assert no_csrf.status_code == 403
    assert alice.get(f"/api/notes/{note['id'] + 1000}", headers=headers).status_code == 404
    assert bob.get(f"/api/notes/{note['id']}", headers=bob_headers).status_code == 404
    patched = alice.patch(
        f"/api/notes/{note['id']}",
        json={"content": "今天的晚霞真好看，改一下", "entry_date": "2026-09-15"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["entry_date"] == "2026-09-15"
    assert alice.delete(f"/api/notes/{note['id']}", headers=headers).status_code == 204
    assert alice.get("/api/notes", headers=headers).json() == []
    # Bob's own notes are invisible to alice and included in bob's export.
    bob.post(
        "/api/notes",
        json={"content": "bob 的私记", "entry_date": "2026-09-16"},
        headers=bob_headers,
    )
    export = bob.get("/api/export", headers=bob_headers).json()
    assert [row["content"] for row in export["notes"]] == ["bob 的私记"]
    assert alice.get("/api/export", headers=headers).json()["notes"] == []


def test_import_round_trips_notes(accounts):
    _, _, _, alice, headers, _, _ = accounts
    alice.post(
        "/api/notes",
        json={"content": "要搬家的备忘", "entry_date": "2026-09-10"},
        headers=headers,
    )
    export = alice.get("/api/export", headers=headers).json()
    result = alice.post("/api/import", json=export, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"]["notes"] == 1
    notes = alice.get("/api/notes", headers=headers).json()
    assert [row["content"] for row in notes] == ["要搬家的备忘"]


def test_migrate_0002_to_0003_keeps_accounts_and_maintenance(tmp_path):
    settings = Settings(tmp_path / "legacy")
    engine = make_engine(settings)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
    with session_factory(engine)() as db:
        user = User(
            username="admin",
            display_name="老用户",
            is_admin=True,
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()
        db.add(Task(user_id=user.id, title="升级前待办", created_at=datetime(2026, 1, 1)))
        db.commit()
    old_backup = tmp_path / "before-notes.db"
    backup(settings, old_backup)
    with sqlite3.connect(old_backup) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0002",)
    migrate(settings)
    engine.dispose()
    with TestClient(create_app(settings.data_dir)) as client:
        csrf = sign_in(client)
        assert client.get("/api/tasks").json()[0]["title"] == "升级前待办"
        assert client.get("/api/notes").json() == []
        created = client.post(
            "/api/notes",
            json={"content": "升级后的第一条随记", "entry_date": "2026-09-16"},
            headers=csrf,
        )
        assert created.status_code == 201
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0007",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    # A 0002 snapshot no longer restores into this version without matching code.
    with pytest.raises(ValueError):
        restore(Settings(tmp_path / "wrong-version"), old_backup)
