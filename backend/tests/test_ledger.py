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
