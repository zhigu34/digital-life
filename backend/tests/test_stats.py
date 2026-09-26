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


def ledger_account(client, headers, name="统计用卡", opening_balance_cents=0, currency="CNY"):
    response = client.post(
        "/api/ledger/accounts",
        json={"name": name, "currency": currency, "opening_balance_cents": opening_balance_cents},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def ledger_category(client, headers, name, kind):
    response = client.post(
        "/api/ledger/categories", json={"name": name, "kind": kind}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def ledger_payee(client, headers, name):
    response = client.post("/api/ledger/payees", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def ledger_entry(client, headers, **overrides):
    payload = {
        "occurred_on": "2026-09-05",
        "kind": "expense",
        "amount_cents": 100,
        "currency": "CNY",
    }
    payload.update(overrides)
    response = client.post("/api/ledger/entries", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_stats_reports_actual_ledger_money_beside_the_projected_dues(accounts):
    _, _, _, alice, headers, bob, bob_headers = accounts
    card = ledger_account(alice, headers)
    wallet = ledger_account(alice, headers, name="统计现金")
    living = ledger_category(alice, headers, "统计居住", "expense")
    salary = ledger_category(alice, headers, "统计工资", "income")
    isp = ledger_payee(alice, headers, "中国联通")

    ledger_entry(
        alice,
        headers,
        amount_cents=3000,
        account_id=card["id"],
        category_id=living["id"],
        payee_id=isp["id"],
    )
    ledger_entry(
        alice,
        headers,
        kind="income",
        amount_cents=500000,
        account_id=card["id"],
        category_id=salary["id"],
    )
    # Uncategorised spending still counts as money out, just not per category.
    ledger_entry(alice, headers, amount_cents=500, account_id=card["id"])
    # Moving money between own accounts is neither income nor spending.
    ledger_entry(
        alice,
        headers,
        kind="transfer",
        amount_cents=700,
        from_account_id=card["id"],
        to_account_id=wallet["id"],
    )
    # Inside the window but outside the end month: only its own month moves.
    ledger_entry(alice, headers, occurred_on="2026-08-10", amount_cents=999, account_id=card["id"])

    result = alice.get("/api/stats", params={"end_month": "2026-09"}, headers=headers)
    assert result.status_code == 200, result.text
    spent = read_month(result, "ledger_expense")
    earned = read_month(result, "ledger_income")
    assert spent["2026-09"] == 3000 + 500
    assert earned["2026-09"] == 500000
    assert spent["2026-08"] == 999
    assert earned["2026-08"] == 0
    assert spent["2025-10"] == 0

    ledger = result.json()["ledger"]
    by_name = {row["name"]: row for row in ledger["categories"]}
    # Only the end month lands in the category breakdown, and no bill is invented.
    assert set(by_name) == {"统计居住", "统计工资"}
    assert by_name["统计居住"]["totals"] == {"CNY": 3000}
    assert by_name["统计居住"]["kind"] == "expense"
    assert by_name["统计工资"]["totals"] == {"CNY": 500000}

    payees = ledger["payees"]
    assert payees[0] == {"payee_id": isp["id"], "name": "中国联通", "totals": {"CNY": 3000}}
    assert payees[1] == {"payee_id": None, "name": "未标注商户", "totals": {"CNY": 500}}

    bob_ledger = bob.get("/api/stats", params={"end_month": "2026-09"}, headers=bob_headers).json()[
        "ledger"
    ]
    assert bob_ledger == {"categories": [], "payees": []}


def test_stats_scopes_money_and_projected_dues_to_one_book(accounts):
    _, _, _, alice, headers, _, _ = accounts
    reno = alice.post("/api/ledger/books", json={"name": "装修"}, headers=headers).json()
    card = alice.post(
        "/api/ledger/accounts",
        json={"name": "招行储蓄卡", "currency": "CNY", "opening_balance_cents": 0},
        headers=headers,
    ).json()

    ledger_entry(alice, headers, amount_cents=320000, account_id=card["id"], book_id=reno["id"])
    # Filed under no book: it belongs to the whole ledger, not to whichever book
    # happens to be open.
    ledger_entry(alice, headers, amount_cents=5800, account_id=card["id"])
    for title, amount, book in (("装修贷", 500000, reno["id"]), ("宽带费", 12900, None)):
        payload = {
            "title": title,
            "amount_cents": amount,
            "period_months": 1,
            "next_due": "2026-09-20",
        }
        if book is not None:
            payload["book_id"] = book
        response = alice.post("/api/expenses", json=payload, headers=headers)
        assert response.status_code == 201, response.text

    def september(response):
        return next(row for row in response.json()["months"] if row["month"] == "2026-09")

    everything = alice.get("/api/stats", params={"end_month": "2026-09"}, headers=headers)
    assert september(everything)["ledger_expense"] == {"CNY": 325800}
    assert september(everything)["expense_due"] == {"CNY": 512900}

    reno_only = alice.get(
        "/api/stats", params={"end_month": "2026-09", "book_id": reno["id"]}, headers=headers
    )
    assert september(reno_only)["ledger_expense"] == {"CNY": 320000}
    assert september(reno_only)["expense_due"] == {"CNY": 500000}
