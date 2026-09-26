import sqlite3
from datetime import date

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from test_auth import PASSWORD, sign_in

from app.config import Settings
from app.database import ROOT, make_engine, migrate
from app.main import create_app
from app.security import hash_password
from app.timezones import user_today

# The `accounts` fixture creates users in the default timezone.
TODAY = user_today("Asia/Shanghai")


def create_group(client, headers, title="健身计划", items=None):
    return client.post(
        "/api/groups",
        headers=headers,
        json={
            "title": title,
            "items": items
            if items is not None
            else [
                {"title": "跑步 30 分钟", "repeat_unit": "day"},
                {"title": "力量训练", "repeat_unit": "week"},
            ],
        },
    )


def test_group_log_lists_recent_completions_with_item_titles(accounts):
    _, _, _, alice, headers, bob, bob_headers = accounts
    group = create_group(alice, headers).json()
    running, strength = group["items"]
    alice.post(
        f"/api/groups/{group['id']}/items/{running['id']}/complete",
        headers=headers,
        json={"on": "2026-09-24", "note": "慢跑"},
    )
    alice.post(
        f"/api/groups/{group['id']}/items/{strength['id']}/complete",
        headers=headers,
        json={"on": "2026-09-26"},
    )
    alice.post(
        f"/api/groups/{group['id']}/items/{running['id']}/complete",
        headers=headers,
        json={"on": "2026-09-26"},
    )

    log = alice.get(f"/api/groups/{group['id']}/log", headers=headers)
    assert log.status_code == 200, log.text
    rows = log.json()
    # Newest first, across every item of the group.
    assert [row["completed_on"] for row in rows] == ["2026-09-26", "2026-09-26", "2026-09-24"]
    assert {row["item_title"] for row in rows} == {"跑步 30 分钟", "力量训练"}
    assert rows[2]["note"] == "慢跑"
    assert all(row["item_id"] in {running["id"], strength["id"]} for row in rows)

    assert len(alice.get(f"/api/groups/{group['id']}/log?limit=1", headers=headers).json()) == 1
    oversized = alice.get(f"/api/groups/{group['id']}/log?limit=51", headers=headers)
    assert oversized.status_code == 422
    # Ownership: another account cannot read the log of a group it does not own.
    assert bob.get(f"/api/groups/{group['id']}/log", headers=bob_headers).status_code == 404
    assert bob.get("/api/groups/9999/log", headers=bob_headers).status_code == 404


def test_group_items_and_completion_periods(accounts):
    _, _, _, alice, headers, bob, bob_headers = accounts
    assert (
        alice.post("/api/groups", headers=headers, json={"title": "空组", "items": []}).status_code
        == 422
    )
    invalid = create_group(alice, headers, items=[{"title": "随便", "repeat_unit": "year"}])
    assert invalid.status_code == 422

    created = create_group(alice, headers)
    assert created.status_code == 201, created.text
    group = created.json()
    assert group["archived"] is False and group["archived_on"] is None
    assert [item["repeat_unit"] for item in group["items"]] == ["day", "week"]
    item = group["items"][0]
    # The period starts today: earlier days were never expected.
    assert item["start_date"] == TODAY.isoformat()
    assert item["recent_days"] == [] and item["total_count"] == 0

    checked = alice.post(
        f"/api/groups/{group['id']}/items/{item['id']}/complete", headers=headers, json={}
    )
    assert checked.status_code == 201, checked.text
    assert checked.json()["total_count"] == 1
    assert checked.json()["recent_days"] == [TODAY.isoformat()]
    duplicate = alice.post(
        f"/api/groups/{group['id']}/items/{item['id']}/complete", headers=headers, json={}
    )
    assert duplicate.status_code == 409

    # A week item is satisfied by any day inside that week, so extra days in the
    # same period are recorded and counted without changing anything else.
    week_item = group["items"][1]
    for checked_on in ("2026-09-14", "2026-09-16", "2026-09-20"):
        response = alice.post(
            f"/api/groups/{group['id']}/items/{week_item['id']}/complete",
            headers=headers,
            json={"on": checked_on, "note": "练了背"},
        )
        assert response.status_code == 201, response.text
    assert response.json()["total_count"] == 3
    assert response.json()["recent_days"] == ["2026-09-14", "2026-09-16", "2026-09-20"]

    future = alice.post(
        f"/api/groups/{group['id']}/items/{item['id']}/complete",
        headers=headers,
        json={"on": "2999-01-01"},
    )
    assert future.status_code == 422

    span = alice.get(
        f"/api/groups/{group['id']}/items/{week_item['id']}/completions",
        headers=headers,
        params={"start": "2026-09-01", "end": "2026-09-30"},
    )
    assert span.status_code == 200
    assert [row["completed_on"] for row in span.json()] == [
        "2026-09-20",
        "2026-09-16",
        "2026-09-14",
    ]
    assert span.json()[0]["note"] == "练了背"
    assert (
        alice.get(
            f"/api/groups/{group['id']}/items/{week_item['id']}/completions",
            headers=headers,
            params={"start": "2026-09-01", "end": "2027-12-31"},
        ).status_code
        == 422
    )
    assert (
        alice.get(
            f"/api/groups/{group['id']}/items/{week_item['id']}/completions",
            headers=headers,
            params={"start": "2026-09-30", "end": "2026-09-01"},
        ).status_code
        == 422
    )

    undo = alice.delete(
        f"/api/groups/{group['id']}/items/{week_item['id']}/complete/2026-09-20", headers=headers
    )
    assert undo.status_code == 204
    missing = alice.delete(
        f"/api/groups/{group['id']}/items/{week_item['id']}/complete/2026-09-20", headers=headers
    )
    assert missing.status_code == 404


def test_group_ownership_csrf_and_nested_lookup(accounts):
    _, admin, admin_headers, alice, headers, bob, bob_headers = accounts
    group = create_group(alice, headers).json()
    item = group["items"][0]

    # CSRF and Origin still guard every write.
    assert create_group(alice, None).status_code == 403
    assert create_group(alice, admin_headers).status_code == 403

    for stranger, csrf in ((bob, bob_headers), (admin, admin_headers)):
        assert stranger.get(f"/api/groups/{group['id']}", headers=csrf).status_code == 404
        assert (
            stranger.patch(
                f"/api/groups/{group['id']}", headers=csrf, json={"title": "stolen"}
            ).status_code
            == 404
        )
        assert stranger.delete(f"/api/groups/{group['id']}", headers=csrf).status_code == 404
        assert (
            stranger.post(
                f"/api/groups/{group['id']}/items/{item['id']}/complete", headers=csrf, json={}
            ).status_code
            == 404
        )
        assert (
            stranger.get(
                f"/api/groups/{group['id']}/items/{item['id']}/completions",
                headers=csrf,
                params={"start": "2026-09-01", "end": "2026-09-30"},
            ).status_code
            == 404
        )
    assert bob.get("/api/groups", headers=bob_headers).json() == []
    assert bob.get("/api/export", headers=bob_headers).json()["task_groups"] == []

    # An item is only reachable through its own group, so a mismatched pair is a
    # 404 rather than a silent write into someone else's item.
    other = create_group(alice, headers, title="读书 · 学习").json()
    assert (
        alice.patch(
            f"/api/groups/{other['id']}/items/{item['id']}", headers=headers, json={"title": "x"}
        ).status_code
        == 404
    )
    assert (
        alice.delete(
            f"/api/groups/{other['id']}/items/{item['id']}/complete/{TODAY.isoformat()}",
            headers=headers,
        ).status_code
        == 404
    )


def test_group_archive_patch_and_cascade_delete(accounts):
    app, _, _, alice, headers, _, _ = accounts
    group = create_group(alice, headers).json()
    item = group["items"][0]
    alice.post(f"/api/groups/{group['id']}/items/{item['id']}/complete", headers=headers, json={})

    archived = alice.patch(f"/api/groups/{group['id']}", headers=headers, json={"archived": True})
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived"] is True
    assert archived.json()["archived_on"] == TODAY.isoformat()
    blocked = alice.post(
        f"/api/groups/{group['id']}/items/{item['id']}/complete", headers=headers, json={}
    )
    assert blocked.status_code == 400

    # Editing an archived group must not move the archiving day.
    renamed = alice.patch(
        f"/api/groups/{group['id']}", headers=headers, json={"title": "健身计划（暂停）"}
    ).json()
    assert renamed["archived_on"] == TODAY.isoformat()

    reopened = alice.patch(
        f"/api/groups/{group['id']}", headers=headers, json={"archived": False}
    ).json()
    assert reopened["archived"] is False and reopened["archived_on"] is None
    assert (
        alice.post(
            f"/api/groups/{group['id']}/items/{item['id']}/complete",
            headers=headers,
            json={"on": "2026-09-20"},
        ).status_code
        == 201
    )

    # A null in the payload never blanks a required field.
    assert (
        alice.patch(
            f"/api/groups/{group['id']}/items/{item['id']}", headers=headers, json={"title": None}
        ).status_code
        == 200
    )
    retitled = alice.patch(
        f"/api/groups/{group['id']}/items/{item['id']}",
        headers=headers,
        json={"repeat_unit": "month"},
    )
    assert retitled.json()["repeat_unit"] == "month"

    assert (
        alice.delete(f"/api/groups/{group['id']}/items/{item['id']}", headers=headers).status_code
        == 204
    )
    assert len(alice.get(f"/api/groups/{group['id']}", headers=headers).json()["items"]) == 1

    assert alice.delete(f"/api/groups/{group['id']}", headers=headers).status_code == 204
    assert alice.get("/api/groups", headers=headers).json() == []
    with sqlite3.connect(app.state.settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM task_completions").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM task_group_items").fetchone()[0] == 0
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_group_export_and_import_round_trip(accounts):
    _, _, _, alice, headers, bob, bob_headers = accounts
    group = create_group(alice, headers).json()
    item = group["items"][0]
    alice.post(
        f"/api/groups/{group['id']}/items/{item['id']}/complete",
        headers=headers,
        json={"on": "2026-09-15", "note": "补昨天的"},
    )

    export = alice.get("/api/export", headers=headers).json()
    assert "checkins" not in export and "checkin_logs" not in export
    assert [row["title"] for row in export["task_groups"]] == ["健身计划"]
    assert [row["repeat_unit"] for row in export["task_group_items"]] == ["day", "week"]
    assert [row["completed_on"] for row in export["task_completions"]] == ["2026-09-15"]
    assert export["task_completions"][0]["note"] == "补昨天的"

    result = alice.post("/api/import", json=export, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"]["task_groups"] == 1
    assert result.json()["imported"]["task_group_items"] == 2
    assert result.json()["imported"]["task_completions"] == 1

    restored = alice.get("/api/groups", headers=headers).json()
    assert [row["title"] for row in restored] == ["健身计划"]
    assert restored[0]["items"][0]["recent_days"] == ["2026-09-15"]
    assert restored[0]["items"][0]["total_count"] == 1
    assert bob.get("/api/export", headers=bob_headers).json()["task_groups"] == []


def test_import_accepts_pre_0011_checkin_exports(accounts):
    _, _, _, alice, headers, _, _ = accounts
    legacy = {
        "user": {},
        "tasks": [],
        "expenses": [],
        "shows": [],
        "milestones": [],
        "notes": [],
        "projects": [],
        "checkins": [
            {"id": 1, "title": "健身1小时", "kind": "daily", "active": True},
            {"id": 2, "title": "读书半小时", "kind": "daily", "active": False},
        ],
        "checkin_logs": [
            {"checkin_id": 1, "checked_on": "2026-09-15", "note": "补的"},
            {"checkin_id": 1, "checked_on": "2026-09-16"},
        ],
    }
    result = alice.post("/api/import", json=legacy, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"]["task_groups"] == 2
    assert result.json()["imported"]["task_group_items"] == 2
    assert result.json()["imported"]["task_completions"] == 2

    groups = {row["title"]: row for row in alice.get("/api/groups", headers=headers).json()}
    checked = groups["健身1小时"]["items"][0]
    assert checked["repeat_unit"] == "day"
    # The earliest completion starts the periods, so history gains no fake misses.
    assert checked["start_date"] == "2026-09-15"
    assert checked["total_count"] == 2
    assert groups["读书半小时"]["archived"] is True
    assert groups["读书半小时"]["archived_on"] is None

    for broken in (
        {"checkins": [{"id": 1, "title": "x", "kind": "weekly"}], "checkin_logs": []},
        {
            "checkins": [{"id": 1, "title": "x", "kind": "daily"}],
            "checkin_logs": [{"checkin_id": 9, "checked_on": "2026-09-15"}],
        },
        {
            "checkins": [{"id": 1, "title": "x", "kind": "daily"}],
            "checkin_logs": [
                {"checkin_id": 1, "checked_on": "2026-09-15"},
                {"checkin_id": 1, "checked_on": "2026-09-15"},
            ],
        },
    ):
        assert (
            alice.post("/api/import", json={"user": {}, **broken}, headers=headers).status_code
            == 422
        )


def test_a_rejected_import_leaves_groups_untouched(accounts):
    _, _, _, alice, headers, _, _ = accounts
    group = create_group(alice, headers).json()
    alice.post(
        f"/api/groups/{group['id']}/items/{group['items'][0]['id']}/complete",
        headers=headers,
        json={},
    )

    dangling = {
        "user": {},
        "tasks": [],
        "expenses": [],
        "shows": [],
        "milestones": [],
        "notes": [],
        "projects": [],
        "task_groups": [{"id": 1, "title": "新的长期任务"}],
        "task_group_items": [
            {
                "id": 1,
                "group_id": 9,
                "title": "跑步",
                "repeat_unit": "day",
                "start_date": "2026-09-01",
            }
        ],
        "task_completions": [],
    }
    rejected = alice.post("/api/import", json=dangling, headers=headers)
    assert rejected.status_code == 422

    surviving = alice.get("/api/groups", headers=headers).json()
    assert [row["title"] for row in surviving] == ["健身计划"]
    assert surviving[0]["items"][0]["total_count"] == 1
    assert surviving[0]["items"][1]["total_count"] == 0


def test_group_list_does_not_query_per_group(accounts):
    """The list endpoint must not grow a query per group or per item."""
    app, _, _, alice, headers, _, _ = accounts
    engine = app.state.engine
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def selects_for(groups):
        statements.clear()
        sa.event.listen(engine, "before_cursor_execute", record)
        try:
            response = alice.get("/api/groups", headers=headers)
        finally:
            sa.event.remove(engine, "before_cursor_execute", record)
        assert response.status_code == 200, response.text
        assert len(response.json()) == groups
        return len([row for row in statements if row.lstrip().upper().startswith("SELECT")])

    for index in range(3):
        create_group(alice, headers, title=f"分组 {index}")
    few = selects_for(3)
    for index in range(3, 9):
        create_group(alice, headers, title=f"分组 {index}")
    many = selects_for(9)
    assert few == many


def test_migrate_0005_to_0011_turns_checkins_into_groups(tmp_path):
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
        for title, created_at in (
            ("健身", "2026-09-01 00:00:00.000000"),
            ("冥想", "2026-09-20 00:00:00.000000"),
        ):
            connection.execute(
                sa.text(
                    "INSERT INTO checkins (user_id, title, notes, kind, active, created_at) "
                    "VALUES (:user_id, :title, '', 'daily', 1, :created_at)"
                ),
                {"user_id": user_id, "title": title, "created_at": created_at},
            )
        checkin_id = connection.execute(
            sa.text("SELECT id FROM checkins WHERE title = '健身'")
        ).scalar()
        for checked_on in ("2026-09-16", "2026-09-17"):
            connection.execute(
                sa.text(
                    "INSERT INTO checkin_logs (checkin_id, checked_on, note, created_at) "
                    "VALUES (:checkin_id, :checked_on, '', :created_at)"
                ),
                {
                    "checkin_id": checkin_id,
                    "checked_on": checked_on,
                    "created_at": f"{checked_on} 00:00:00.000000",
                },
            )
    migrate(settings)
    engine.dispose()

    with TestClient(create_app(settings.data_dir)) as client:
        csrf = sign_in(client)
        groups = {row["title"]: row for row in client.get("/api/groups", headers=csrf).json()}
        assert set(groups) == {"健身", "冥想"}
        checked = groups["健身"]["items"][0]
        assert checked["repeat_unit"] == "day"
        # Started by its first completion, not by the creation timestamp.
        assert checked["start_date"] == "2026-09-16"
        assert checked["recent_days"] == ["2026-09-16", "2026-09-17"]
        assert checked["total_count"] == 2
        never_checked = groups["冥想"]["items"][0]
        assert never_checked["start_date"] == "2026-09-20"
        assert never_checked["total_count"] == 0
        # The new API is usable right after the migration.
        assert create_group(client, csrf, title="新的长期任务").status_code == 201

    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0011",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        leftover = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name IN ('checkins', 'checkin_logs')"
        ).fetchone()[0]
        assert leftover == 0
        assert db.execute("SELECT COUNT(*) FROM task_completions").fetchone()[0] == 2


def test_migration_downgrade_writes_checkins_back(tmp_path):
    settings = Settings(tmp_path / "legacy")
    engine = make_engine(settings)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0011")
        connection.execute(
            sa.text(
                "INSERT INTO users "
                "(username, password_hash, display_name, timezone, theme, is_admin, is_active) "
                "VALUES ('admin', :password_hash, '回退用户', 'Asia/Shanghai', 'light', 1, 1)"
            ),
            {"password_hash": hash_password(PASSWORD)},
        )
        user_id = connection.execute(sa.text("SELECT id FROM users")).scalar()
        connection.execute(
            sa.text(
                "INSERT INTO task_groups "
                "(user_id, title, notes, archived, archived_on, created_at) "
                "VALUES (:user_id, '健身计划', '', 0, NULL, '2026-09-01 00:00:00.000000')"
            ),
            {"user_id": user_id},
        )
        group_id = connection.execute(sa.text("SELECT id FROM task_groups")).scalar()
        connection.execute(
            sa.text(
                "INSERT INTO task_group_items "
                "(group_id, title, repeat_unit, start_date, created_at) "
                "VALUES (:group_id, '跑步', 'day', '2026-09-02', '2026-09-01 00:00:00.000000')"
            ),
            {"group_id": group_id},
        )
        item_id = connection.execute(sa.text("SELECT id FROM task_group_items")).scalar()
        connection.execute(
            sa.text(
                "INSERT INTO task_completions (item_id, completed_on, note, created_at) "
                "VALUES (:item_id, '2026-09-02', '跑了 5 公里', '2026-09-02 00:00:00.000000')"
            ),
            {"item_id": item_id},
        )
        command.downgrade(config, "0010")

    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0010",)
        assert db.execute("SELECT title, kind, active FROM checkins").fetchall() == [
            ("跑步", "daily", 1)
        ]
        assert db.execute("SELECT checked_on, note FROM checkin_logs").fetchall() == [
            ("2026-09-02", "跑了 5 公里")
        ]
        columns = {row[1] for row in db.execute("PRAGMA table_info('tasks')")}
        assert "completed_on" not in columns


def test_one_off_tasks_have_no_period_fields(accounts):
    """One-off to-dos and long-term groups are separate shapes by design."""
    _, _, _, alice, headers, _, _ = accounts
    for extra in ({"repeat_unit": "day"}, {"start_date": "2026-09-01"}, {"kind": "recurring"}):
        response = alice.post("/api/tasks", headers=headers, json={"title": "待办", **extra})
        assert response.status_code == 422
    created = alice.post("/api/tasks", headers=headers, json={"title": "交房租"}).json()
    assert created["completed_on"] is None
    assert date.fromisoformat(created["created_at"][:10]) <= TODAY
