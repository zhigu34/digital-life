from test_auth import sign_in  # noqa: F401


def build_export(client, headers):
    client.post(
        "/api/tasks",
        json={
            "title": "导出的待办",
            "status": "doing",
            "due_date": "2026-10-01",
            "priority": "high",
        },
        headers=headers,
    ).json()
    client.post(
        "/api/expenses",
        json={
            "title": "导出的费用",
            "amount_cents": 12000,
            "period_months": 12,
            "next_due": "2026-09-20",
        },
        headers=headers,
    ).json()
    client.post(
        "/api/shows",
        json={"title": "导出的作品", "status": "watching", "progress": 3, "total": 12},
        headers=headers,
    ).json()
    client.post(
        "/api/milestones",
        json={"title": "导出的日子", "date": "2020-09-21", "repeats_yearly": True},
        headers=headers,
    ).json()
    maintenance = client.post(
        "/api/maintenance",
        json={
            "title": "导出的滤芯",
            "last_completed": "2026-01-31",
            "period_value": 1,
            "period_unit": "months",
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/maintenance/{maintenance['id']}/complete",
        json={"completed_on": "2026-03-31", "cost_cents": 12950, "currency": "CNY"},
        headers=headers,
    ).json()
    export = client.get("/api/export", headers=headers).json()
    assert export["maintenance"][0]["next_due"] == "2026-04-30"
    return export


def test_import_replaces_account_data_from_export(accounts):
    _, _, _, alice, headers, _, _ = accounts
    export = build_export(alice, headers)
    # Replace requires CSRF; without it the request is rejected.
    assert alice.post("/api/import", json=export).status_code == 403
    result = alice.post("/api/import", json=export, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"] == {
        "tasks": 1,
        "expenses": 1,
        "shows": 1,
        "milestones": 1,
        "notes": 0,
        "maintenance": 1,
        "maintenance_logs": 2,
        "checkins": 0,
        "checkin_logs": 0,
    }
    # Importing twice replaces instead of duplicating.
    again = alice.post("/api/import", json=export, headers=headers)
    assert again.status_code == 200
    tasks = alice.get("/api/tasks", headers=headers).json()
    assert len(tasks) == 1 and tasks[0]["title"] == "导出的待办"
    items = alice.get("/api/maintenance", headers=headers).json()
    assert len(items) == 1
    assert items[0]["last_completed"] == "2026-03-31"
    assert items[0]["next_due"] == "2026-04-30"
    history = alice.get(f"/api/maintenance/{items[0]['id']}/history", headers=headers).json()
    assert [log["completed_on"] for log in history] == ["2026-03-31", "2026-01-31"]
    assert history[0]["cost_cents"] == 12950


def test_import_accepts_pre_maintenance_exports_and_validates_rows(accounts):
    _, _, _, alice, headers, _, _ = accounts
    legacy = {
        "user": {"username": "alice"},
        "tasks": [{"title": "旧版本待办", "status": "todo"}],
        "expenses": [],
        "shows": [],
        "milestones": [],
    }
    result = alice.post("/api/import", json=legacy, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"]["maintenance"] == 0
    titles = [task["title"] for task in alice.get("/api/tasks", headers=headers).json()]
    assert titles == ["旧版本待办"]

    for bad in (
        {"tasks": []},  # missing user marker
        {"user": {}, "tasks": {"nope": True}},  # not a list
        {"user": {}, "expenses": [{"title": "缺金额", "next_due": "2026-09-01"}]},
        {
            "user": {},
            "tasks": [{"title": "x"}],
            "maintenance": [
                {
                    "title": "m",
                    "last_completed": "2026-01-01",
                    "period_value": 1,
                    "period_unit": "months",
                }
            ],
            "maintenance_logs": [{"completed_on": "2026-01-05", "maintenance_id": 999}],
        },
        {"user": {}},  # nothing to import
    ):
        response = alice.post("/api/import", json=bad, headers=headers)
        assert response.status_code == 422, bad


def test_import_rejects_duplicate_history_days(accounts):
    _, _, _, alice, headers, _, _ = accounts
    payload = {
        "user": {},
        "tasks": [],
        "expenses": [],
        "shows": [],
        "milestones": [],
        "maintenance": [
            {
                "id": 5,
                "title": "滤芯",
                "last_completed": "2026-01-31",
                "period_value": 1,
                "period_unit": "months",
            }
        ],
        "maintenance_logs": [
            {"id": 1, "maintenance_id": 5, "completed_on": "2026-01-31"},
            {"id": 2, "maintenance_id": 5, "completed_on": "2026-01-31"},
        ],
    }
    response = alice.post("/api/import", json=payload, headers=headers)
    assert response.status_code == 422
    # A failed import leaves the existing data untouched.
    assert alice.get("/api/maintenance", headers=headers).json() == []


def test_import_only_touches_the_callers_account(accounts):
    _, _, _, alice, alice_headers, bob, bob_headers = accounts
    export = build_export(alice, alice_headers)
    bob_task = bob.post("/api/tasks", json={"title": "bob 自己的待办"}, headers=bob_headers).json()
    result = bob.post("/api/import", json=export, headers=bob_headers)
    assert result.status_code == 200
    tasks = bob.get("/api/tasks", headers=bob_headers).json()
    assert [task["title"] for task in tasks] == ["导出的待办"]
    # Alice imported nothing; her own export content is still hers alone.
    alice_tasks = alice.get("/api/tasks", headers=alice_headers).json()
    assert [task["title"] for task in alice_tasks] == ["导出的待办"]
    assert bob_task["title"] not in [task["title"] for task in tasks]
