import sqlite3
from datetime import date, datetime

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from test_auth import PASSWORD, sign_in

from app.config import Settings
from app.database import ROOT, make_engine, migrate, session_factory
from app.main import create_app
from app.models import CheckIn, CheckInLog, User
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
    alice.post("/api/checkins", json={"title": "健身", "kind": "daily"}, headers=headers)
    export = alice.get("/api/export", headers=headers).json()
    result = alice.post("/api/import", json=export, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"]["projects"] == 1
    assert result.json()["imported"]["checkins"] == 1
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
    assert converted.json()["imported"]["checkins"] == 1
    assert converted.json()["imported"]["projects"] == 1
    projects = alice.get("/api/projects", headers=headers).json()
    assert [row["title"] for row in projects] == ["旧在做项"]
    assert "原打卡 2 条（2026-09-15 ~ 2026-09-16）" in projects[0]["notes"]
    assert "背景说明" in projects[0]["notes"]


def test_migrate_0005_to_0006_moves_ongoing_checkins_to_projects(tmp_path):
    settings = Settings(tmp_path / "legacy")
    engine = make_engine(settings)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0005")
    with session_factory(engine)() as db:
        user = User(
            username="admin",
            display_name="迁移用户",
            is_admin=True,
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()
        daily = CheckIn(
            user_id=user.id,
            kind="daily",
            active=True,
            created_at=datetime(2026, 9, 1),
            title="健身",
        )
        ongoing = CheckIn(
            user_id=user.id,
            kind="ongoing",
            active=True,
            created_at=datetime(2026, 9, 2),
            title="项目开发",
            notes="背景",
        )
        db.add_all([daily, ongoing])
        db.flush()
        db.add_all(
            [
                CheckInLog(
                    checkin_id=ongoing.id,
                    checked_on=date(2026, 9, 15),
                    note="",
                    created_at=datetime(2026, 9, 15),
                ),
                CheckInLog(
                    checkin_id=ongoing.id,
                    checked_on=date(2026, 9, 16),
                    note="",
                    created_at=datetime(2026, 9, 16),
                ),
                CheckInLog(
                    checkin_id=daily.id,
                    checked_on=date(2026, 9, 16),
                    note="",
                    created_at=datetime(2026, 9, 16),
                ),
            ]
        )
        db.commit()
    migrate(settings)
    engine.dispose()
    with TestClient(create_app(settings.data_dir)) as client:
        csrf = sign_in(client)
        projects = client.get("/api/projects", headers=csrf).json()
        assert [row["title"] for row in projects] == ["项目开发"]
        assert "背景" in projects[0]["notes"]
        assert "原打卡 2 条（2026-09-15 ~ 2026-09-16）" in projects[0]["notes"]
        checkins = client.get("/api/checkins", headers=csrf).json()
        assert [row["title"] for row in checkins] == ["健身"]
        assert checkins[0]["total_count"] == 1
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0010",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        leftover = db.execute("SELECT COUNT(*) FROM checkin_logs").fetchone()[0]
        assert leftover == 1
