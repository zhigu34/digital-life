"""Ledger endpoints: ownership isolation, validation, derived balances and merging."""

from datetime import date, timedelta


def recent(days=3):
    return (date.today() - timedelta(days=days)).isoformat()


def future(days=3):
    return (date.today() + timedelta(days=days)).isoformat()


def make_account(client, headers, name="招行储蓄卡", **overrides):
    payload = {"name": name, "kind": "debit", "currency": "CNY", "opening_balance_cents": 100000}
    payload.update(overrides)
    response = client.post("/api/ledger/accounts", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def make_category(client, headers, name="餐饮", kind="expense", **overrides):
    payload = {"name": name, "kind": kind}
    payload.update(overrides)
    response = client.post("/api/ledger/categories", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def make_payee(client, headers, name="老张面馆", **overrides):
    payload = {"name": name}
    payload.update(overrides)
    response = client.post("/api/ledger/payees", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def make_entry(client, headers, **overrides):
    payload = {"occurred_on": recent(), "kind": "expense", "amount_cents": 2000, "currency": "CNY"}
    payload.update(overrides)
    response = client.post("/api/ledger/entries", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def balances_of(client, headers):
    return {row["id"]: row["balance_cents"] for row in client.get("/api/ledger/accounts").json()}


def test_account_crud_and_derived_balance(accounts):
    _, _, _, alice, ah, _, _ = accounts
    account = make_account(alice, ah, name="  招行储蓄卡  ", opening_balance_cents=-50000)
    assert account["name"] == "招行储蓄卡"
    assert account["balance_cents"] == -50000

    updated = alice.patch(
        f"/api/ledger/accounts/{account['id']}",
        json={"name": "招行信用卡", "archived": True, "opening_balance_cents": -1000},
        headers=ah,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "招行信用卡"
    assert updated.json()["archived"] is True
    assert updated.json()["balance_cents"] == -1000

    assert alice.delete(f"/api/ledger/accounts/{account['id']}", headers=ah).status_code == 204
    assert alice.get(f"/api/ledger/accounts/{account['id']}").status_code == 404


def test_account_balance_follows_entries(accounts):
    _, _, _, alice, ah, _, _ = accounts
    wallet = make_account(alice, ah, name="现金", opening_balance_cents=100000)
    card = make_account(alice, ah, name="招行储蓄卡", opening_balance_cents=0)

    make_entry(alice, ah, kind="income", amount_cents=50000, account_id=wallet["id"])
    make_entry(alice, ah, kind="expense", amount_cents=20000, account_id=wallet["id"])
    make_entry(
        alice,
        ah,
        kind="transfer",
        amount_cents=30000,
        from_account_id=wallet["id"],
        to_account_id=card["id"],
    )

    assert balances_of(alice, ah) == {wallet["id"]: 100000, card["id"]: 30000}


def test_account_balance_bounds(accounts):
    _, _, _, alice, ah, _, _ = accounts
    oversized = alice.post(
        "/api/ledger/accounts",
        json={"name": "现金", "opening_balance_cents": 1_000_000_001},
        headers=ah,
    )
    assert oversized.status_code == 422


def test_account_delete_blocked_when_referenced(accounts):
    _, _, _, alice, ah, _, _ = accounts
    account = make_account(alice, ah)
    make_entry(alice, ah, account_id=account["id"])
    assert alice.delete(f"/api/ledger/accounts/{account['id']}", headers=ah).status_code == 409


def test_default_categories_seeded_once(accounts):
    _, _, _, alice, ah, bob, bh = accounts
    seeded = alice.get("/api/ledger/categories").json()
    assert {row["kind"] for row in seeded} == {"income", "expense"}
    assert any(row["name"] == "餐饮" for row in seeded)

    make_category(alice, ah, name="宠物")
    second = alice.get("/api/ledger/categories").json()
    assert len(second) == len(seeded) + 1
    assert sum(row["name"] == "餐饮" for row in second) == 1

    # Seeding is per user, so another account gets its own untouched set.
    assert bob.get("/api/ledger/categories").json()[0]["name"] in {"工资", "餐饮"}


def test_category_rules(accounts):
    _, _, _, alice, ah, _, _ = accounts
    category = make_category(alice, ah, name="餐饮")
    duplicate = alice.post(
        "/api/ledger/categories", json={"name": "餐饮", "kind": "expense"}, headers=ah
    )
    assert duplicate.status_code == 409
    assert (
        alice.post(
            "/api/ledger/categories", json={"name": "餐饮", "kind": "income"}, headers=ah
        ).status_code
        == 201
    )

    kind_change = alice.patch(
        f"/api/ledger/categories/{category['id']}", json={"kind": "income"}, headers=ah
    )
    assert kind_change.status_code == 422

    make_entry(alice, ah, account_id=make_account(alice, ah)["id"], category_id=category["id"])
    assert alice.delete(f"/api/ledger/categories/{category['id']}", headers=ah).status_code == 409


def test_entry_validation(accounts):
    _, _, _, alice, ah, _, _ = accounts
    card = make_account(alice, ah, name="储蓄卡")
    dollars = make_account(alice, ah, name="美元账户", currency="USD")
    expense_category = make_category(alice, ah, name="餐饮")

    def post(payload):
        return alice.post("/api/ledger/entries", json=payload, headers=ah)

    base = {"occurred_on": recent(), "kind": "expense", "amount_cents": 100}
    assert post({**base, "amount_cents": 0, "account_id": card["id"]}).status_code == 422
    assert post({**base, "account_id": card["id"], "occurred_on": future()}).status_code == 422
    assert post({**base, "account_id": None}).status_code == 422
    assert post({**base, "currency": "USD", "account_id": card["id"]}).status_code == 422
    assert (
        post(
            {
                **base,
                "kind": "income",
                "account_id": card["id"],
                "category_id": expense_category["id"],
            }
        ).status_code
        == 422
    )
    transfer = {"occurred_on": recent(), "kind": "transfer", "amount_cents": 100}
    assert (
        post({**transfer, "from_account_id": card["id"], "to_account_id": card["id"]}).status_code
        == 422
    )
    assert (
        post(
            {
                **transfer,
                "from_account_id": card["id"],
                "to_account_id": dollars["id"],
            }
        ).status_code
        == 422
    )
    assert (
        post(
            {
                **transfer,
                "from_account_id": card["id"],
                "to_account_id": card["id"] + 1,
                "account_id": card["id"],
            }
        ).status_code
        == 422
    )


def test_entry_window_and_filters(accounts):
    _, _, _, alice, ah, _, _ = accounts
    card = make_account(alice, ah)
    cash = make_account(alice, ah, name="现金")
    stale = make_entry(
        alice,
        ah,
        occurred_on=(date.today() - timedelta(days=800)).isoformat(),
        account_id=card["id"],
    )
    purchase = make_entry(alice, ah, account_id=card["id"])
    transfer = make_entry(
        alice,
        ah,
        kind="transfer",
        amount_cents=100,
        from_account_id=card["id"],
        to_account_id=cash["id"],
    )

    default = alice.get("/api/ledger/entries").json()
    ids = {row["id"] for row in default}
    assert purchase["id"] in ids
    assert transfer["id"] in ids
    assert stale["id"] not in ids

    # A transfer counts as activity on either side even though it is not spending.
    on_card = alice.get("/api/ledger/entries", params={"account_id": card["id"]}).json()
    assert {row["id"] for row in on_card} == {purchase["id"], transfer["id"]}
    only_transfers = alice.get("/api/ledger/entries", params={"kind": "transfer"}).json()
    assert [row["id"] for row in only_transfers] == [transfer["id"]]


def test_entry_update_and_delete(accounts):
    _, _, _, alice, ah, _, _ = accounts
    card = make_account(alice, ah)
    entry = make_entry(alice, ah, account_id=card["id"], amount_cents=2000)

    updated = alice.patch(
        f"/api/ledger/entries/{entry['id']}", json={"amount_cents": 3500}, headers=ah
    )
    assert updated.status_code == 200
    assert updated.json()["amount_cents"] == 3500
    assert balances_of(alice, ah)[card["id"]] == 100000 - 3500

    # Switching to a transfer must satisfy the transfer field rules.
    assert (
        alice.patch(
            f"/api/ledger/entries/{entry['id']}", json={"kind": "transfer"}, headers=ah
        ).status_code
        == 422
    )

    assert alice.delete(f"/api/ledger/entries/{entry['id']}", headers=ah).status_code == 204
    assert alice.get(f"/api/ledger/entries/{entry['id']}").status_code == 404


def test_payee_dictionary_and_merge(accounts):
    _, _, _, alice, ah, bob, bh = accounts
    shop = make_payee(alice, ah, name=" 老张面馆 ")
    assert shop["name"] == "老张面馆"
    assert (
        alice.post("/api/ledger/payees", json={"name": "老张面馆"}, headers=ah).status_code == 409
    )
    # Another account may reuse the same name.
    assert bob.post("/api/ledger/payees", json={"name": "老张面馆"}, headers=bh).status_code == 201

    make_payee(alice, ah, name="楼下便利店")
    found = alice.get("/api/ledger/payees", params={"keyword": "便利店"}).json()
    assert [row["name"] for row in found] == ["楼下便利店"]

    card = make_account(alice, ah)
    make_entry(alice, ah, account_id=card["id"], payee_id=shop["id"])
    assert alice.delete(f"/api/ledger/payees/{shop['id']}", headers=ah).status_code == 409

    target = make_payee(alice, ah, name="张记面馆")
    merged = alice.post(
        f"/api/ledger/payees/{shop['id']}/merge", json={"into": target["id"]}, headers=ah
    )
    assert merged.status_code == 200
    assert merged.json() == {"entries": 1, "expenses": 0}
    assert alice.get(f"/api/ledger/payees/{shop['id']}").status_code == 404
    # The entry survived the merge and still blocks deleting the target.
    assert alice.delete(f"/api/ledger/payees/{target['id']}", headers=ah).status_code == 409

    assert (
        alice.post(
            f"/api/ledger/payees/{target['id']}/merge",
            json={"into": target["id"]},
            headers=ah,
        ).status_code
        == 422
    )
    foreign = make_payee(bob, bh, name="别人家")
    assert (
        alice.post(
            f"/api/ledger/payees/{target['id']}/merge", json={"into": foreign["id"]}, headers=ah
        ).status_code
        == 404
    )


def test_ownership_isolation(accounts):
    _, _, _, alice, ah, bob, bh = accounts
    account = make_account(alice, ah)
    category = make_category(alice, ah, name="餐饮")
    payee = make_payee(alice, ah)
    entry = make_entry(alice, ah, account_id=account["id"])

    patches = {
        f"/api/ledger/accounts/{account['id']}": {"name": "偷来的"},
        f"/api/ledger/categories/{category['id']}": {"name": "偷来的"},
        f"/api/ledger/payees/{payee['id']}": {"name": "偷来的"},
        f"/api/ledger/entries/{entry['id']}": {"amount_cents": 1},
    }
    for path, payload in patches.items():
        assert bob.get(path).status_code == 404
        assert bob.patch(path, json=payload, headers=bh).status_code == 404
        assert bob.delete(path, headers=bh).status_code == 404

    assert bob.get("/api/ledger/accounts").json() == []
    assert bob.get("/api/ledger/entries").json() == []


def test_ledger_requires_session_and_validates_input(accounts):
    _, _, _, alice, ah, _, _ = accounts
    assert alice.post("/api/ledger/accounts", json={"name": "现金"}).status_code == 403
    assert (
        alice.post(
            "/api/ledger/accounts", json={"name": "现金", "extra": 1}, headers=ah
        ).status_code
        == 422
    )
    assert alice.get("/api/ledger/entries", params={"limit": 5000}).status_code == 422
    assert alice.get("/api/ledger/entries", params={"limit": 0}).status_code == 422

    alice.cookies.clear()
    assert alice.get("/api/ledger/accounts").status_code == 401


# --------------------------------------------------------------------------- #
# Confirming a recurring bill as paid: the optional ledger link.
# --------------------------------------------------------------------------- #


def make_bill(client, headers, **overrides):
    payload = {
        "title": "宽带费",
        "amount_cents": 12900,
        "currency": "CNY",
        "period_months": 1,
        "next_due": "2026-09-20",
    }
    payload.update(overrides)
    response = client.post("/api/expenses", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def confirm_pay(client, headers, bill_id, body=None):
    return client.post(f"/api/expenses/{bill_id}/pay", json=body, headers=headers)


def due_of(client, headers, bill_id):
    response = client.get(f"/api/expenses/{bill_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["next_due"]


def test_pay_without_account_only_advances_the_due_date(accounts):
    _, _, _, alice, ah, _, _ = accounts
    bill = make_bill(alice, ah)

    response = confirm_pay(alice, ah, bill["id"])
    assert response.status_code == 200, response.text
    assert response.json()["entry_id"] is None
    assert response.json()["next_due"] == "2026-10-20"
    assert alice.get("/api/ledger/entries").json() == []


def test_pay_with_bound_account_posts_a_matching_entry(accounts):
    _, _, _, alice, ah, _, _ = accounts
    card = make_account(alice, ah, opening_balance_cents=100000)
    category = make_category(alice, ah, name="宽带分类")
    payee = make_payee(alice, ah, name="中国联通")
    bill = make_bill(
        alice, ah, account_id=card["id"], category_id=category["id"], payee_id=payee["id"]
    )
    assert bill["account_id"] == card["id"]

    body = confirm_pay(alice, ah, bill["id"]).json()
    assert body["next_due"] == "2026-10-20"
    assert body["entry_id"] is not None

    rows = alice.get("/api/ledger/entries").json()
    assert len(rows) == 1
    entry = rows[0]
    assert entry["id"] == body["entry_id"]
    assert entry["expense_id"] == bill["id"]
    assert entry["kind"] == "expense"
    assert entry["amount_cents"] == 12900
    assert entry["currency"] == "CNY"
    assert entry["account_id"] == card["id"]
    assert entry["category_id"] == category["id"]
    assert entry["payee_id"] == payee["id"]
    # Defaults to "today" in the profile zone, so allow for the UTC/UTC+8 skew.
    today = date.today()
    assert entry["occurred_on"] in {today.isoformat(), (today + timedelta(days=1)).isoformat()}
    assert balances_of(alice, ah)[card["id"]] == 100000 - 12900


def test_pay_request_body_overrides_the_bill_defaults(accounts):
    _, _, _, alice, ah, _, _ = accounts
    bill_account = make_account(alice, ah, name="招行储蓄卡", opening_balance_cents=100000)
    other = make_account(alice, ah, name="支付宝余额", opening_balance_cents=50000)
    bill = make_bill(alice, ah, account_id=bill_account["id"])
    category = make_category(alice, ah, name="宽带分类")

    body = confirm_pay(
        alice,
        ah,
        bill["id"],
        {"occurred_on": recent(1), "account_id": other["id"], "category_id": category["id"]},
    ).json()
    entry = alice.get("/api/ledger/entries").json()[0]
    assert body["entry_id"] == entry["id"]
    assert entry["account_id"] == other["id"]
    assert entry["category_id"] == category["id"]
    assert entry["occurred_on"] == recent(1)
    balances = balances_of(alice, ah)
    assert balances[other["id"]] == 50000 - 12900
    assert balances[bill_account["id"]] == 100000


def test_pay_rejects_bad_reference_and_keeps_the_due_date(accounts):
    _, _, _, alice, ah, bob, bh = accounts
    card = make_account(alice, ah)
    bill = make_bill(alice, ah, account_id=card["id"])
    foreign = make_account(bob, bh, name="bob 的卡")

    assert confirm_pay(alice, ah, bill["id"], {"account_id": foreign["id"]}).status_code == 422
    # A refused link must not leave a bill that moved on without recording it.
    assert due_of(alice, ah, bill["id"]) == "2026-09-20"
    assert alice.get("/api/ledger/entries").json() == []

    income = make_category(alice, ah, name="工资", kind="income")
    assert confirm_pay(alice, ah, bill["id"], {"category_id": income["id"]}).status_code == 422
    assert due_of(alice, ah, bill["id"]) == "2026-09-20"


def test_pay_rejects_an_inactive_bill(accounts):
    _, _, _, alice, ah, _, _ = accounts
    card = make_account(alice, ah)
    bill = make_bill(alice, ah, account_id=card["id"], active=False)

    assert confirm_pay(alice, ah, bill["id"]).status_code == 400
    assert alice.get("/api/ledger/entries").json() == []


def test_deleting_a_bill_keeps_its_entry(accounts):
    _, _, _, alice, ah, _, _ = accounts
    card = make_account(alice, ah)
    bill = make_bill(alice, ah, account_id=card["id"])
    confirm_pay(alice, ah, bill["id"])

    assert alice.delete(f"/api/expenses/{bill['id']}", headers=ah).status_code == 204
    rows = alice.get("/api/ledger/entries").json()
    assert len(rows) == 1
    assert rows[0]["expense_id"] is None
    # The entry still counts as activity, so the account cannot be deleted.
    assert alice.delete(f"/api/ledger/accounts/{card['id']}", headers=ah).status_code == 409


def test_bill_defaults_must_belong_to_the_caller(accounts):
    _, _, _, alice, ah, bob, bh = accounts
    foreign = make_account(bob, bh, name="bob 的卡")
    payload = {"title": "宽带费", "amount_cents": 12900, "next_due": "2026-09-20"}

    created = alice.post("/api/expenses", json={**payload, "account_id": foreign["id"]}, headers=ah)
    assert created.status_code == 422

    income = make_category(alice, ah, name="工资", kind="income")
    wrong_kind = alice.post(
        "/api/expenses", json={**payload, "category_id": income["id"]}, headers=ah
    )
    assert wrong_kind.status_code == 422

    # Null keeps the pre-ledger behaviour and stays patchable.
    bill = alice.post("/api/expenses", json={**payload, "account_id": None}, headers=ah)
    assert bill.status_code == 201
    bill_id = bill.json()["id"]
    account = make_account(alice, ah)
    assert (
        alice.patch(
            f"/api/expenses/{bill_id}", json={"account_id": foreign["id"]}, headers=ah
        ).status_code
        == 422
    )
    assert (
        alice.patch(
            f"/api/expenses/{bill_id}", json={"account_id": account["id"]}, headers=ah
        ).status_code
        == 200
    )
