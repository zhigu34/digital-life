from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import pytest

BASE = {
    "title": "净水器滤芯",
    "period_value": 1,
    "period_unit": "months",
    "last_completed": "2024-01-31",
    "remind_days": 7,
}


def create_item(client, csrf, **changes):
    response = client.post("/api/maintenance", headers=csrf, json={**BASE, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_maintenance_initial_history_and_config_patch(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah, notes="使用原装滤芯")
    path = f"/api/maintenance/{item['id']}"
    assert item["last_completed"] == "2024-01-31"
    assert item["next_due"] == "2024-02-29"
    assert item["active"] is True
    assert "user_id" not in item
    assert alice.get(path).json() == item
    assert alice.get("/api/maintenance").json() == [item]
    history = alice.get(path + "/history").json()
    assert len(history) == 1
    assert history[0]["completed_on"] == "2024-01-31"
    assert history[0]["maintenance_id"] == item["id"]
    assert history[0]["cost_cents"] is None and history[0]["currency"] == "CNY"
    assert "user_id" not in history[0]
    changed = alice.patch(
        path, headers=ah, json={"period_value": 30, "period_unit": "days", "title": "新名称"}
    )
    assert changed.status_code == 200
    assert changed.json()["next_due"] == "2024-03-01"
    assert changed.json()["last_completed"] == "2024-01-31"
    for field in ("last_completed", "next_due", "user_id", "id"):
        assert alice.patch(path, headers=ah, json={field: "2024-02-01"}).status_code == 422


def test_maintenance_owner_isolation_csrf_and_export(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    path = f"/api/maintenance/{item['id']}"
    log_id = alice.get(path + "/history").json()[0]["id"]
    for stranger, csrf in ((bob, bh), (admin, headers)):
        assert stranger.get("/api/maintenance").json() == []
        assert stranger.get(path).status_code == 404
        assert stranger.get(path + "/history").status_code == 404
        assert stranger.patch(path, headers=csrf, json={"title": "steal"}).status_code == 404
        assert stranger.delete(path, headers=csrf).status_code == 404
        assert (
            stranger.post(
                path + "/complete", headers=csrf, json={"completed_on": "2024-02-01"}
            ).status_code
            == 404
        )
        assert (
            stranger.patch(
                path + f"/history/{log_id}", headers=csrf, json={"notes": "steal"}
            ).status_code
            == 404
        )
        exported = stranger.get("/api/export").json()
        assert exported["maintenance"] == [] and exported["maintenance_logs"] == []
    assert alice.post("/api/maintenance", json=BASE).status_code == 403
    assert alice.patch(path, json={"title": "no csrf"}).status_code == 403
    assert alice.delete(path).status_code == 403
    assert alice.post(path + "/complete", json={"completed_on": "2024-02-01"}).status_code == 403
    assert alice.patch(path + f"/history/{log_id}", json={"notes": "x"}).status_code == 403
    exported = alice.get("/api/export").json()
    assert exported["maintenance"] == [item]
    assert exported["maintenance_logs"][0]["id"] == log_id
    second = create_item(alice, ah, title="同账号另一个事项")
    assert (
        alice.patch(
            f"/api/maintenance/{second['id']}/history/{log_id}",
            headers=ah,
            json={"notes": "wrong parent"},
        ).status_code
        == 404
    )


def test_complete_uses_actual_month_day_and_backfill_does_not_rewind(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah, last_completed="2023-01-31")
    path = f"/api/maintenance/{item['id']}"
    result = alice.post(
        path + "/complete",
        headers=ah,
        json={
            "completed_on": "2023-02-28",
            "cost_cents": 15000,
            "currency": "HKD",
            "notes": "换芯",
        },
    )
    assert result.status_code == 201
    assert result.json()["next_due"] == "2023-03-28"
    assert (
        alice.post(path + "/complete", headers=ah, json={"completed_on": "2023-01-15"}).json()[
            "last_completed"
        ]
        == "2023-02-28"
    )
    history = alice.get(path + "/history").json()
    assert [row["completed_on"] for row in history] == ["2023-02-28", "2023-01-31", "2023-01-15"]
    assert history[0]["cost_cents"] == 15000 and history[0]["notes"] == "换芯"
    assert (
        alice.post(path + "/complete", headers=ah, json={"completed_on": "2023-02-28"}).status_code
        == 409
    )
    assert len(alice.get(path + "/history").json()) == 3


def test_history_correction_recomputes_max_and_conflicts_are_atomic(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    path = f"/api/maintenance/{item['id']}"
    alice.post(path + "/complete", headers=ah, json={"completed_on": "2024-03-01"})
    latest, initial = alice.get(path + "/history").json()
    latest_path = path + f"/history/{latest['id']}"
    result = alice.patch(
        latest_path,
        headers=ah,
        json={"completed_on": "2024-01-10", "cost_cents": 0, "notes": "改正日期"},
    )
    assert result.status_code == 200
    assert result.json()["last_completed"] == "2024-01-31"
    assert result.json()["next_due"] == "2024-02-29"
    assert (
        alice.patch(
            latest_path, headers=ah, json={"completed_on": "2024-01-31", "notes": "should not save"}
        ).status_code
        == 409
    )
    saved = next(x for x in alice.get(path + "/history").json() if x["id"] == latest["id"])
    assert saved["completed_on"] == "2024-01-10" and saved["notes"] == "改正日期"
    assert alice.patch(latest_path, headers=ah, json={"cost_cents": None}).status_code == 200
    assert alice.delete(latest_path, headers=ah).status_code == 405


def test_inactive_items_keep_editable_history_but_cannot_complete(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah, active=False)
    path = f"/api/maintenance/{item['id']}"
    assert (
        alice.post(path + "/complete", headers=ah, json={"completed_on": "2024-02-01"}).status_code
        == 400
    )
    first = alice.get(path + "/history").json()[0]
    result = alice.patch(
        path + f"/history/{first['id']}", headers=ah, json={"completed_on": "2024-02-01"}
    )
    assert result.status_code == 200 and result.json()["next_due"] == "2024-03-01"


def test_concurrent_duplicate_completion_creates_one_log(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    path = f"/api/maintenance/{item['id']}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: alice.post(
                    path + "/complete", headers=ah, json={"completed_on": "2024-02-29"}
                ),
                range(2),
            )
        )
    assert sorted(x.status_code for x in responses) == [201, 409]
    assert len(alice.get(path + "/history").json()) == 2
    assert alice.get(path).json()["next_due"] == "2024-03-29"


def test_delete_cascades_history_in_database(accounts):
    from sqlalchemy import text

    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    assert alice.delete(f"/api/maintenance/{item['id']}", headers=ah).status_code == 204
    assert alice.get("/api/maintenance").json() == []
    assert alice.get("/api/export").json()["maintenance_logs"] == []
    with app.state.engine.connect() as db:
        assert db.execute(text("SELECT count(*) FROM maintenance_logs")).scalar() == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"period_value": True},
        {"period_value": 0},
        {"period_value": 3651, "period_unit": "days"},
        {"period_value": 121},
        {"period_unit": "years"},
        {"remind_days": True},
        {"remind_days": 366},
        {"last_completed": "2024-02-30"},
        {"last_completed": "9999-12-31"},
        {"last_completed": 1700000000},
        {"title": ""},
        {"user_id": 1},
        {"next_due": "2025-01-01"},
    ],
)
def test_invalid_maintenance_creation(accounts, changes):
    app, admin, headers, alice, ah, bob, bh = accounts
    assert alice.post("/api/maintenance", headers=ah, json={**BASE, **changes}).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"completed_on": "9999-12-31"},
        {"completed_on": "2024-02-30"},
        {"cost_cents": True},
        {"cost_cents": -1},
        {"cost_cents": 100000001},
        {"currency": "BTC"},
        {"maintenance_id": 1},
        {"user_id": 1},
        {"created_at": "2024-01-01T00:00:00"},
    ],
)
def test_invalid_completion_and_history_patch(accounts, changes):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    path = f"/api/maintenance/{item['id']}"
    log_id = alice.get(path + "/history").json()[0]["id"]
    assert (
        alice.post(
            path + "/complete", headers=ah, json={"completed_on": "2024-02-01", **changes}
        ).status_code
        == 422
    )
    assert alice.patch(path + f"/history/{log_id}", headers=ah, json=changes).status_code == 422


def test_period_patch_validates_merged_unit_and_nulls(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah, period_value=365, period_unit="days")
    path = f"/api/maintenance/{item['id']}"
    assert alice.patch(path, headers=ah, json={"period_unit": "months"}).status_code == 422
    for field in ("title", "period_value", "period_unit", "remind_days", "active", "notes"):
        assert alice.patch(path, headers=ah, json={field: None}).status_code == 422
    result = alice.patch(path, headers=ah, json={"period_value": 120, "period_unit": "months"})
    assert result.status_code == 200 and result.json()["next_due"] == "2034-01-31"


def test_calendar_computation_rejects_overflow_and_handles_leap_day():
    from app.maintenance import next_due_date

    assert next_due_date(date(2024, 2, 29), 12, "months") == date(2025, 2, 28)
    assert next_due_date(date(2024, 3, 9), 2, "days") == date(2024, 3, 11)
    for unit in ("months", "days"):
        with pytest.raises(ValueError):
            next_due_date(date(9999, 12, 31), 1, unit)


def test_future_date_validation_uses_user_timezone_and_legacy_utc(accounts, monkeypatch):
    from sqlalchemy import select

    import app.maintenance as module
    import app.timezones as timezone_module
    from app.models import User

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2024, 5, 1, 0, 30, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(module, "datetime", FixedDateTime)
    # "Today" is derived by the shared timezone helper, so freeze its clock too.
    monkeypatch.setattr(timezone_module, "datetime", FixedDateTime)
    app, admin, headers, alice, ah, bob, bh = accounts
    alice.patch("/api/auth/profile", headers=ah, json={"timezone": "America/Los_Angeles"})
    assert (
        alice.post(
            "/api/maintenance", headers=ah, json={**BASE, "last_completed": "2024-05-01"}
        ).status_code
        == 422
    )
    create_item(alice, ah, last_completed="2024-04-30")
    with app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == "alice"))
        user.timezone = "Factory"
        db.commit()
    create_item(alice, ah, last_completed="2024-05-01")


def test_maintenance_and_history_id_overflow_is_rejected(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    path = f"/api/maintenance/{2**63}"
    assert alice.get(path).status_code == 422
    assert alice.get(path + "/history").status_code == 422
    assert (
        alice.post(path + "/complete", headers=ah, json={"completed_on": "2024-02-01"}).status_code
        == 422
    )
    path = f"/api/maintenance/{item['id']}/history/{2**63}"
    assert alice.patch(path, headers=ah, json={"notes": "x"}).status_code == 422


@pytest.mark.parametrize(
    "unit,initial,last_valid",
    [
        ("days", "9999-12-30", "9999-12-31"),
        ("months", "9999-11-30", "9999-12-30"),
    ],
)
def test_calendar_overflow_rejects_entire_api_mutation(
    accounts, monkeypatch, unit, initial, last_valid
):
    import app.maintenance as module

    monkeypatch.setattr(module, "user_today", lambda timezone: date.max)
    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah, period_unit=unit, last_completed=initial)
    path = f"/api/maintenance/{item['id']}"
    original_history = alice.get(path + "/history").json()
    log_id = original_history[0]["id"]
    assert (
        alice.post(
            "/api/maintenance",
            headers=ah,
            json={
                **BASE,
                "period_unit": unit,
                "last_completed": last_valid,
            },
        ).status_code
        == 422
    )
    assert len(alice.get("/api/maintenance").json()) == 1
    assert (
        alice.post(path + "/complete", headers=ah, json={"completed_on": last_valid}).status_code
        == 422
    )
    assert alice.patch(path, headers=ah, json={"period_value": 2}).status_code == 422
    result = alice.patch(
        path + f"/history/{log_id}",
        headers=ah,
        json={"completed_on": last_valid, "notes": "must rollback"},
    )
    assert result.status_code == 422
    assert alice.get(path).json() == item
    assert alice.get(path + "/history").json() == original_history


def test_maintenance_authentication_required(accounts):
    from fastapi.testclient import TestClient

    app, admin, headers, alice, ah, bob, bh = accounts
    item = create_item(alice, ah)
    path = f"/api/maintenance/{item['id']}"
    log_id = alice.get(path + "/history").json()[0]["id"]
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/maintenance").status_code == 401
        assert anonymous.get(path).status_code == 401
        assert anonymous.get(path + "/history").status_code == 401
        assert anonymous.post("/api/maintenance", json=BASE).status_code == 401
        assert anonymous.patch(path, json={"title": "x"}).status_code == 401
        assert anonymous.delete(path).status_code == 401
        assert (
            anonymous.post(path + "/complete", json={"completed_on": "2024-02-01"}).status_code
            == 401
        )
        assert anonymous.patch(path + f"/history/{log_id}", json={"notes": "x"}).status_code == 401
