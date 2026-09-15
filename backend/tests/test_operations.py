import os
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from test_auth import PASSWORD, sign_in

from app.main import create_app


def run_cli(directory, *args, password=None):
    env = {**os.environ, "DIGITAL_LIFE_DATA_DIR": str(directory)}
    if password:
        env["DIGITAL_LIFE_ADMIN_PASSWORD"] = password
    return subprocess.run(
        [sys.executable, "-m", "app.cli", *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_migrate_admin_and_restart(tmp_path):
    data = tmp_path / "data"
    for _ in range(2):
        result = run_cli(data, "migrate")
        assert result.returncode == 0, result.stderr
    result = run_cli(data, "create-admin", "--username", "admin", password=PASSWORD)
    assert result.returncode == 0, result.stderr
    assert PASSWORD not in result.stdout + result.stderr
    assert run_cli(data, "create-admin", "--username", "admin", password=PASSWORD).returncode != 0
    with TestClient(create_app(data)) as client:
        csrf = sign_in(client)
        client.post("/api/tasks", headers=csrf, json={"title": "持久化"})
    with TestClient(create_app(data)) as restarted:
        sign_in(restarted)
        assert restarted.get("/api/tasks").json()[0]["title"] == "持久化"
    with sqlite3.connect(data / "digital-life.db") as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def test_online_backup_and_offline_restore_preserve_records(accounts, tmp_path):
    from app.cli import backup, restore

    app, admin, headers, alice, ah, bob, bh = accounts
    alice.post("/api/tasks", headers=ah, json={"title": "备份之前"})
    dest = tmp_path / "saved.db"
    backup(app.state.settings, dest)
    alice.post("/api/tasks", headers=ah, json={"title": "备份之后"})
    # Restore into an offline, independent data directory: no live process owns it.
    fresh = create_app(tmp_path / "restored")
    restore(fresh.state.settings, dest)
    with TestClient(fresh) as client:
        sign_in(client, "alice")
        assert [x["title"] for x in client.get("/api/tasks").json()] == ["备份之前"]


@pytest.mark.parametrize(
    "kind", ["junk", "foreign_schema", "broken_foreign_keys", "missing_column"]
)
def test_restore_rejects_invalid_database_without_modifying_live_data(accounts, tmp_path, kind):
    from app.cli import backup, restore

    app, admin, headers, alice, ah, bob, bh = accounts
    alice.post("/api/tasks", headers=ah, json={"title": "保留"})
    candidate = tmp_path / f"{kind}.db"
    if kind == "junk":
        candidate.write_bytes(b"not sqlite")
    elif kind == "foreign_schema":
        with sqlite3.connect(candidate) as db:
            db.execute("CREATE TABLE unrelated (id INTEGER)")
    else:
        backup(app.state.settings, candidate)
        with sqlite3.connect(candidate) as db:
            if kind == "broken_foreign_keys":
                db.execute("UPDATE tasks SET user_id = 999999")
            else:
                db.execute("ALTER TABLE tasks DROP COLUMN notes")
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        restore(app.state.settings, candidate)
    assert alice.get("/api/tasks").json()[0]["title"] == "保留"


def test_health_checks_database_and_security_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("DIGITAL_LIFE_SECURE_COOKIE", "true")
    monkeypatch.setenv("DIGITAL_LIFE_TRUSTED_ORIGINS", "https://life.example")
    from app.cli import create_admin

    app = create_app(tmp_path)
    with TestClient(app, base_url="https://testserver") as client:
        create_admin(app.state.settings, "admin", PASSWORD)
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": PASSWORD},
            headers={"Origin": "https://life.example"},
        )
        assert login.status_code == 200
        assert "Secure" in login.headers["set-cookie"]
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "admin", "password": PASSWORD},
                headers={"Origin": "https://evil.example", "X-Forwarded-Host": "evil.example"},
            ).status_code
            == 403
        )
        with app.state.engine.begin() as db:
            db.exec_driver_sql("DROP TABLE users")
        assert client.get("/health").status_code == 503


def test_health_fails_if_business_table_is_missing(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        with app.state.engine.begin() as db:
            db.exec_driver_sql("DROP TABLE tasks")
        assert client.get("/health").status_code == 503


def test_restoring_backup_does_not_revive_sessions(accounts, tmp_path):
    from app.cli import backup, restore

    app, admin, headers, alice, ah, bob, bh = accounts
    cookie = alice.cookies.get("digital_life_session")
    destination = tmp_path / "snapshot.db"
    backup(app.state.settings, destination)
    fresh = create_app(tmp_path / "fresh")
    restore(fresh.state.settings, destination)
    with TestClient(fresh) as client:
        client.cookies.set("digital_life_session", cookie)
        assert client.get("/api/auth/session").status_code == 401
        sign_in(client, "alice")


def test_new_cli_can_back_up_older_schema_before_upgrade(tmp_path):
    from app.cli import backup
    from app.config import Settings

    settings = Settings(tmp_path / "old")
    settings.data_dir.mkdir()
    with sqlite3.connect(settings.database_path) as db:
        db.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        db.execute("INSERT INTO alembic_version VALUES ('older-version')")
        db.execute("CREATE TABLE old_records (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        db.execute("INSERT INTO old_records VALUES (1, 'keep this')")
    destination = tmp_path / "before-upgrade.db"
    backup(settings, destination)
    with sqlite3.connect(destination) as db:
        assert db.execute("SELECT title FROM old_records").fetchall() == [("keep this",)]
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "older-version"
        )
