import sqlite3

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from test_auth import PASSWORD, sign_in

from app.config import Settings
from app.database import ROOT, make_engine, migrate, session_factory
from app.main import create_app
from app.models import User
from app.security import hash_password


def test_checkin_crud_and_daily_uniqueness(accounts):
    _, _, _, alice, headers, bob, bob_headers = accounts
    created = alice.post(
        "/api/checkins",
        json={"title": "健身1小时", "kind": "daily"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["kind"] == "daily" and item["days"] == [] and item["total_count"] == 0

    first = alice.post(f"/api/checkins/{item['id']}/check", json={}, headers=headers)
    assert first.status_code == 201, first.text
    assert first.json()["total_count"] == 1
    duplicate = alice.post(f"/api/checkins/{item['id']}/check", json={}, headers=headers)
    assert duplicate.status_code == 409
    # Makeup entries may target past dates, never the future.
    makeup = alice.post(
        f"/api/checkins/{item['id']}/check",
        json={"checked_on": "2026-09-15", "note": "补昨天的"},
        headers=headers,
    )
    assert makeup.status_code == 201
    assert sorted(makeup.json()["days"]) == ["2026-09-15", makeup.json()["days"][-1]]
    future = alice.post(
        f"/api/checkins/{item['id']}/check", json={"checked_on": "2999-01-01"}, headers=headers
    )
    assert future.status_code == 422

    undo = alice.delete(f"/api/checkins/{item['id']}/check/2026-09-15", headers=headers)
    assert undo.status_code == 204
    missing = alice.delete(f"/api/checkins/{item['id']}/check/2026-09-15", headers=headers)
    assert missing.status_code == 404

    # CSRF, ownership and visibility.
    assert alice.post("/api/checkins", json={"title": "x", "kind": "daily"}).status_code == 403
    logs = bob.get(f"/api/checkins/{item['id']}/logs", headers=bob_headers)
    assert logs.status_code == 404
    foreign = bob.post(f"/api/checkins/{item['id']}/check", json={}, headers=bob_headers)
    assert foreign.status_code == 404
    export = alice.get("/api/export", headers=headers).json()
    assert [row["title"] for row in export["checkins"]] == ["健身1小时"]
    assert len(export["checkin_logs"]) == 1
    assert bob.get("/api/export", headers=bob_headers).json()["checkins"] == []


def test_checkin_patch_archive_and_cascade_delete(accounts):
    _, _, _, alice, headers, _, _ = accounts
    rejected = alice.post(
        "/api/checkins", json={"title": "项目开发", "kind": "ongoing"}, headers=headers
    )
    assert rejected.status_code == 422  # ongoing items live in projects now
    item = alice.post(
        "/api/checkins", json={"title": "读书半小时", "kind": "daily"}, headers=headers
    ).json()
    alice.post(f"/api/checkins/{item['id']}/check", json={}, headers=headers)
    patched = alice.patch(
        f"/api/checkins/{item['id']}",
        json={"title": "Side project", "active": False},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Side project" and patched.json()["active"] is False
    blocked = alice.post(f"/api/checkins/{item['id']}/check", json={}, headers=headers)
    assert blocked.status_code == 400
    assert alice.delete(f"/api/checkins/{item['id']}", headers=headers).status_code == 204
    assert alice.get("/api/checkins", headers=headers).json() == []


def test_checkin_import_round_trip_and_validation(accounts):
    _, _, _, alice, headers, _, _ = accounts
    item = alice.post(
        "/api/checkins", json={"title": "健身1小时", "kind": "daily"}, headers=headers
    ).json()
    alice.post(
        f"/api/checkins/{item['id']}/check", json={"checked_on": "2026-09-15"}, headers=headers
    )
    export = alice.get("/api/export", headers=headers).json()
    result = alice.post("/api/import", json=export, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"]["checkins"] == 1
    assert result.json()["imported"]["checkin_logs"] == 1
    restored = alice.get("/api/checkins", headers=headers).json()
    assert restored[0]["days"] == ["2026-09-15"]
    assert restored[0]["total_count"] == 1

    broken = {
        "user": {},
        "checkins": [{"id": 1, "title": "x", "kind": "weekly"}],
        "checkin_logs": [],
    }
    assert alice.post("/api/import", json=broken, headers=headers).status_code == 422
    dangling = {
        "user": {},
        "checkins": [{"id": 1, "title": "x", "kind": "daily"}],
        "checkin_logs": [{"checkin_id": 9, "checked_on": "2026-09-15"}],
    }
    assert alice.post("/api/import", json=dangling, headers=headers).status_code == 422


def test_migrate_0004_to_0005_keeps_accounts_and_shows(tmp_path):
    settings = Settings(tmp_path / "legacy")
    engine = make_engine(settings)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0004")
    with session_factory(engine)() as db:
        user = User(
            username="admin",
            display_name="升级用户",
            is_admin=True,
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.commit()
    migrate(settings)
    engine.dispose()
    with TestClient(create_app(settings.data_dir)) as client:
        csrf = sign_in(client)
        assert client.get("/api/checkins", headers=csrf).json() == []
        created = client.post(
            "/api/checkins", json={"title": "健身", "kind": "daily"}, headers=csrf
        )
        assert created.status_code == 201
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0009",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
