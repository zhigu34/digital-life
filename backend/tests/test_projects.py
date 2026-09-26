import sqlite3

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from test_auth import PASSWORD, sign_in

from app.config import Settings
from app.database import ROOT, make_engine, migrate
from app.main import create_app
from app.security import hash_password


def test_project_crud_status_and_isolation(accounts):
    _, _, _, alice, headers, bob, bob_headers = accounts
    assert alice.post("/api/projects", json={"notes": "缺标题"}, headers=headers).status_code == 422
    created = alice.post(
        "/api/projects", json={"title": "项目开发", "notes": "生活工作台"}, headers=headers
    )
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["status"] == "active"
    paused = alice.patch(
        f"/api/projects/{project['id']}", json={"status": "paused"}, headers=headers
    )
    assert paused.json()["status"] == "paused"
    done = alice.patch(
        f"/api/projects/{project['id']}",
        json={"status": "done", "notes": "v1 上线"},
        headers=headers,
    )
    assert done.json()["notes"] == "v1 上线"
    assert bob.get(f"/api/projects/{project['id']}", headers=bob_headers).status_code == 404
    assert (
        bob.patch(
            f"/api/projects/{project['id']}", json={"title": "x"}, headers=bob_headers
        ).status_code
        == 404
    )
    assert alice.delete(f"/api/projects/{project['id']}", headers=headers).status_code == 204
    export = alice.get("/api/export", headers=headers).json()
    assert export["projects"] == []
    assert bob.get("/api/export", headers=bob_headers).json()["projects"] == []


def test_project_import_round_trip_and_legacy_ongoing_conversion(accounts):
    _, _, _, alice, headers, _, _ = accounts
    alice.post("/api/projects", json={"title": "项目开发"}, headers=headers)
    alice.post(
        "/api/groups",
        json={"title": "健身", "items": [{"title": "健身", "repeat_unit": "day"}]},
        headers=headers,
    )
    export = alice.get("/api/export", headers=headers).json()
    result = alice.post("/api/import", json=export, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"]["projects"] == 1
    assert result.json()["imported"]["task_groups"] == 1
    titles = [row["title"] for row in alice.get("/api/projects", headers=headers).json()]
    assert titles == ["项目开发"]

    legacy = {
        "user": {},
        "tasks": [],
        "expenses": [],
        "shows": [],
        "milestones": [],
        "notes": [],
        "projects": [],
        "checkins": [
            {"id": 1, "title": "健身", "kind": "daily"},
            {"id": 2, "title": "旧在做项", "kind": "ongoing", "notes": "背景说明"},
        ],
        "checkin_logs": [
            {"checkin_id": 2, "checked_on": "2026-09-15"},
            {"checkin_id": 2, "checked_on": "2026-09-16"},
        ],
    }
    converted = alice.post("/api/import", json=legacy, headers=headers)
    assert converted.status_code == 200, converted.text
    assert converted.json()["imported"]["task_groups"] == 1
    assert converted.json()["imported"]["projects"] == 1
    projects = alice.get("/api/projects", headers=headers).json()
    assert [row["title"] for row in projects] == ["旧在做项"]
    assert "原打卡 2 条（2026-09-15 ~ 2026-09-16）" in projects[0]["notes"]
    assert "背景说明" in projects[0]["notes"]


def test_migrate_0005_to_head_splits_ongoing_and_daily_items(tmp_path):
    settings = Settings(tmp_path / "legacy")
    engine = make_engine(settings)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0005")
        connection.execute(
            sa.text(
                "INSERT INTO users "
                "(username, password_hash, display_name, timezone, theme, is_admin, is_active) "
                "VALUES ('admin', :password_hash, '迁移用户', 'Asia/Shanghai', 'light', 1, 1)"
            ),
            {"password_hash": hash_password(PASSWORD)},
        )
        user_id = connection.execute(sa.text("SELECT id FROM users")).scalar()
        for title, kind, notes, created_at in (
            ("健身", "daily", "", "2026-09-01 00:00:00.000000"),
            ("项目开发", "ongoing", "背景", "2026-09-02 00:00:00.000000"),
        ):
            connection.execute(
                sa.text(
                    "INSERT INTO checkins (user_id, title, notes, kind, active, created_at) "
                    "VALUES (:user_id, :title, :notes, :kind, 1, :created_at)"
                ),
                {
                    "user_id": user_id,
                    "title": title,
                    "notes": notes,
                    "kind": kind,
                    "created_at": created_at,
                },
            )
        for title, checked_on in (
            ("项目开发", "2026-09-15"),
            ("项目开发", "2026-09-16"),
            ("健身", "2026-09-16"),
        ):
            connection.execute(
                sa.text(
                    "INSERT INTO checkin_logs (checkin_id, checked_on, note, created_at) "
                    "SELECT id, :checked_on, '', :created_at FROM checkins WHERE title = :title"
                ),
                {
                    "title": title,
                    "checked_on": checked_on,
                    "created_at": f"{checked_on} 00:00:00.000000",
                },
            )
    migrate(settings)
    engine.dispose()
    with TestClient(create_app(settings.data_dir)) as client:
        csrf = sign_in(client)
        projects = client.get("/api/projects", headers=csrf).json()
        assert [row["title"] for row in projects] == ["项目开发"]
        assert "背景" in projects[0]["notes"]
        assert "原打卡 2 条（2026-09-15 ~ 2026-09-16）" in projects[0]["notes"]
        groups = client.get("/api/groups", headers=csrf).json()
        assert [row["title"] for row in groups] == ["健身"]
        assert groups[0]["items"][0]["total_count"] == 1
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0011",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
