from test_auth import sign_in  # noqa: F401


def read_month(result, key, currency="CNY"):
    return {entry["month"]: entry[key].get(currency, 0) for entry in result.json()["months"]}


def test_stats_requires_authentication(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/stats", params={"end_month": "2026-09"}).status_code == 401


def test_stats_rejects_malformed_months(accounts):
    _, _, _, alice, headers, _, _ = accounts
    # Missing parameter is validated after authentication in this app.
    assert alice.get("/api/stats", headers=headers).status_code == 422
    for value in ("2026-9", "2026-13", "abcd-ef", "2026/09", "2026-09-01"):
        response = alice.get("/api/stats", params={"end_month": value}, headers=headers)
        assert response.status_code == 422, value


def test_stats_extrapolates_expense_due_by_period(accounts):
    _, _, _, alice, headers, _, _ = accounts
    # Monthly: every month in the window from 2026-05.
    assert (
        alice.post(
            "/api/expenses",
            json={
                "title": "月费",
                "amount_cents": 3000,
                "period_months": 1,
                "next_due": "2026-05-10",
            },
            headers=headers,
        ).status_code
        == 201
    )
    # Quarterly: 2025-12 is in the window (2025-10..2026-09), so 12, 03, 06, 09 count.
    assert (
        alice.post(
            "/api/expenses",
            json={
                "title": "季费",
                "amount_cents": 9000,
                "period_months": 3,
                "next_due": "2025-12-15",
            },
            headers=headers,
        ).status_code
        == 201
    )
    # Yearly: only 2026-09 lands inside the window.
    assert (
        alice.post(
            "/api/expenses",
            json={
                "title": "年费",
                "amount_cents": 12000,
                "period_months": 12,
                "next_due": "2026-09-20",
            },
            headers=headers,
        ).status_code
        == 201
    )
    # Inactive expenses never count.
    assert (
        alice.post(
            "/api/expenses",
            json={
                "title": "停用",
                "amount_cents": 5000,
                "period_months": 1,
                "next_due": "2026-01-01",
                "active": False,
            },
            headers=headers,
        ).status_code
        == 201
    )
    result = alice.get("/api/stats", params={"end_month": "2026-09"}, headers=headers)
    assert result.status_code == 200, result.text
    due = read_month(result, "expense_due")
    assert len(due) == 12
    assert due["2025-10"] == 0
    # The monthly fee only starts at 2026-05; occurrences never extend backwards.
    assert due["2025-12"] == 9000
    assert due["2026-03"] == 9000
    assert due["2026-04"] == 0
    assert due["2026-05"] == 3000
    assert due["2026-06"] == 3000 + 9000
    assert due["2026-09"] == 3000 + 9000 + 12000


def test_stats_aggregates_maintenance_costs_by_month_and_currency(accounts):
    _, _, _, alice, headers, _, _ = accounts
    created = alice.post(
        "/api/maintenance",
        json={
            "title": "滤芯",
            "last_completed": "2026-08-01",
            "period_value": 1,
            "period_unit": "months",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    # Creation already logged 2026-08-01 for free; add two paid completions.
    for day, cost, currency in ("05", 8000, "CNY"), ("28", 1200, "USD"):
        completed = alice.post(
            f"/api/maintenance/{item_id}/complete",
            json={"completed_on": f"2026-08-{day}", "cost_cents": cost, "currency": currency},
            headers=headers,
        )
        assert completed.status_code == 201, completed.text
    # Same day re-completion would 409; a free log still creates history but no cost.
    extra = alice.post(
        f"/api/maintenance/{item_id}/complete",
        json={"completed_on": "2026-07-20"},
        headers=headers,
    )
    assert extra.status_code == 201, extra.text
    result = alice.get("/api/stats", params={"end_month": "2026-09"}, headers=headers)
    cost_cny = read_month(result, "maintenance_cost")
    cost_usd = read_month(result, "maintenance_cost", "USD")
    assert cost_cny["2026-08"] == 8000
    assert cost_usd["2026-08"] == 1200
    assert cost_cny["2026-09"] == 0


def test_stats_summarizes_shows(accounts):
    _, _, _, alice, headers, _, _ = accounts
    for title, status, progress, total in (
        ("在看一部", "watching", 5, 12),
        ("补完一部", "completed", 26, 26),
        ("想看一部", "planned", 0, None),
    ):
        response = alice.post(
            "/api/shows",
            json={"title": title, "status": status, "progress": progress, "total": total},
            headers=headers,
        )
        assert response.status_code == 201, response.text
    summary = alice.get("/api/stats", params={"end_month": "2026-09"}, headers=headers).json()[
        "shows"
    ]
    assert summary == {
        "watching": 1,
        "planned": 1,
        "completed": 1,
        "paused": 0,
        "episodes_watched": 31,
    }


def test_stats_never_leaks_other_accounts(accounts):
    _, _, _, alice, alice_headers, bob, bob_headers = accounts
    assert (
        alice.post(
            "/api/expenses",
            json={
                "title": "只有 alice 的费用",
                "amount_cents": 4700,
                "period_months": 1,
                "next_due": "2026-09-01",
            },
            headers=alice_headers,
        ).status_code
        == 201
    )
    for client, headers, title in (
        (alice, alice_headers, "alice 的事"),
        (bob, bob_headers, "bob 的事"),
    ):
        response = client.post(
            "/api/maintenance",
            json={
                "title": title,
                "last_completed": "2026-09-01",
                "period_value": 1,
                "period_unit": "months",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
    bob_stats = bob.get("/api/stats", params={"end_month": "2026-09"}, headers=bob_headers)
    assert bob_stats.status_code == 200
    assert all(entry["expense_due"] == {} for entry in bob_stats.json()["months"])
    assert all(entry["maintenance_cost"] == {} for entry in bob_stats.json()["months"])
    alice_stats = alice.get(
        "/api/stats", params={"end_month": "2026-09"}, headers=alice_headers
    ).json()
    assert alice_stats["months"][-1]["expense_due"] == {"CNY": 4700}
