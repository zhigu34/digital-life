import pytest

COLLECTIONS = [
    ("tasks", {"title": "私事"}),
    ("expenses", {"title": "房租", "amount_cents": 120000, "next_due": "2027-01-31"}),
    ("shows", {"title": "作品"}),
    ("milestones", {"title": "纪念日", "date": "2020-02-29"}),
]


@pytest.mark.parametrize("collection,payload", COLLECTIONS)
def test_owner_only_crud_and_export(accounts, collection, payload):
    app, admin, headers, alice, ah, bob, bh = accounts
    created = alice.post("/api/" + collection, headers=ah, json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    assert "user_id" not in item
    path = f"/api/{collection}/{item['id']}"
    assert alice.get(path).json() == item
    assert alice.get("/api/" + collection).json() == [item]
    for stranger, csrf in [(bob, bh), (admin, headers)]:
        assert stranger.get("/api/" + collection).json() == []
        assert stranger.get(path).status_code == 404
        assert stranger.patch(path, headers=csrf, json={"title": "stolen"}).status_code == 404
        assert stranger.delete(path, headers=csrf).status_code == 404
        assert stranger.get("/api/export").json()[collection] == []
    for extra in ("user_id", "id", "created_at"):
        assert (
            alice.post("/api/" + collection, headers=ah, json={**payload, extra: 42}).status_code
            == 422
        )
        assert alice.patch(path, headers=ah, json={extra: 42}).status_code == 422
    assert alice.patch(path, headers=ah, json={"title": "更新"}).json()["title"] == "更新"
    exported = alice.get("/api/export").json()
    assert exported[collection][0]["title"] == "更新"
    assert "password_hash" not in exported["user"]
    assert "sessions" not in exported
    assert alice.delete(path, headers=ah).status_code == 204
    assert alice.get(path).status_code == 404
    assert alice.get("/api/" + collection).json() == []


def test_recurring_dates_and_inactive_payment(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    expense = alice.post(
        "/api/expenses",
        headers=ah,
        json={
            "title": "月末",
            "amount_cents": 100,
            "next_due": "2027-01-31",
        },
    ).json()
    path = f"/api/expenses/{expense['id']}"
    assert expense["anchor_day"] == 31
    assert bob.post(path + "/pay", headers=bh).status_code == 404
    assert alice.post(path + "/pay", headers=ah).json()["next_due"] == "2027-02-28"
    assert alice.post(path + "/pay", headers=ah).json()["next_due"] == "2027-03-31"
    assert (
        alice.patch(
            path, headers=ah, json={"period_months": 12, "next_due": "2028-02-29", "anchor_day": 29}
        ).status_code
        == 200
    )
    assert alice.post(path + "/pay", headers=ah).json()["next_due"] == "2029-02-28"
    alice.patch(path, headers=ah, json={"active": False})
    assert alice.post(path + "/pay", headers=ah).status_code == 400


def test_show_advance_and_combined_patch_validation(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    item = alice.post("/api/shows", headers=ah, json={"title": "三集", "total": 3}).json()
    path = f"/api/shows/{item['id']}"
    assert bob.post(path + "/advance", headers=bh).status_code == 404
    advanced = alice.post(path + "/advance", headers=ah).json()
    assert advanced["progress"] == 1 and advanced["status"] == "watching"
    assert alice.patch(path, headers=ah, json={"total": 0}).status_code == 422
    assert alice.patch(path, headers=ah, json={"progress": 4}).status_code == 422
    assert alice.patch(path, headers=ah, json={"progress": 2, "total": 2}).status_code == 200
    assert alice.post(path + "/advance", headers=ah).json()["progress"] == 2
    alice.patch(path, headers=ah, json={"progress": 1, "status": "watching"})
    advanced = alice.post(path + "/advance", headers=ah).json()
    assert advanced["progress"] == 2 and advanced["status"] == "completed"
    assert advanced["completed_on"] is not None


def test_user_today_respects_profile_timezone():
    from datetime import UTC, date, datetime

    from app.records import user_today

    now = datetime(2026, 9, 17, 6, 30, tzinfo=UTC)
    assert user_today("America/Los_Angeles", now) == date(2026, 9, 16)
    assert user_today("Asia/Shanghai", now) == date(2026, 9, 17)


def test_show_richer_metadata_and_completion_date(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    created = alice.post(
        "/api/shows",
        headers=ah,
        json={
            "title": "作品资料",
            "release_year": 2024,
            "source_url": "https://bgm.tv/subject/123",
            "completed_on": "2024-12-31",
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["release_year"] == 2024
    assert item["source_url"] == "https://bgm.tv/subject/123"
    assert item["completed_on"] == "2024-12-31"

    watching = alice.post(
        "/api/shows", headers=ah, json={"title": "自动完成日期", "status": "watching"}
    ).json()
    path = f"/api/shows/{watching['id']}"
    completed = alice.patch(path, headers=ah, json={"status": "completed"}).json()
    assert completed["completed_on"] is not None
    first_date = completed["completed_on"]
    unchanged = alice.patch(path, headers=ah, json={"title": "仍已完成"}).json()
    assert unchanged["completed_on"] == first_date
    explicit = alice.patch(path, headers=ah, json={"completed_on": "2020-01-02"}).json()
    assert explicit["completed_on"] == "2020-01-02"
    restored = alice.patch(path, headers=ah, json={"completed_on": None}).json()
    assert restored["completed_on"] is not None


@pytest.mark.parametrize(
    "payload",
    [
        {"release_year": 999},
        {"release_year": 10000},
        {"release_year": True},
        {"source_url": "javascript:alert(1)"},
        {"source_url": "ftp://example.com/show"},
    ],
)
def test_show_richer_metadata_rejects_invalid_values(accounts, payload):
    app, admin, headers, alice, ah, bob, bh = accounts
    result = alice.post("/api/shows", headers=ah, json={"title": "非法资料", **payload})
    assert result.status_code == 422


@pytest.mark.parametrize(
    "collection,payload",
    [
        ("tasks", {"title": ""}),
        ("tasks", {"title": "x", "due_date": "2027-02-29"}),
        ("tasks", {"title": "x", "due_date": 1700000000}),
        ("tasks", {"title": "x", "status": "invalid"}),
        ("expenses", {"title": "x", "amount_cents": 0, "next_due": "2027-01-01"}),
        ("expenses", {"title": "x", "amount_cents": 1.2, "next_due": "2027-01-01"}),
        ("expenses", {"title": "x", "amount_cents": True, "next_due": "2027-01-01"}),
        (
            "expenses",
            {"title": "x", "amount_cents": 1, "next_due": "2027-01-01", "period_months": 2},
        ),
        ("shows", {"title": "x", "total": 2, "progress": 3}),
        ("shows", {"title": "x", "score": 11}),
        ("shows", {"title": "x", "update_weekday": 7}),
        ("milestones", {"title": "x", "date": "2026-13-01"}),
    ],
)
def test_invalid_record_payloads(accounts, collection, payload):
    app, admin, headers, alice, ah, bob, bh = accounts
    assert alice.post("/api/" + collection, headers=ah, json=payload).status_code == 422


def test_patch_rejects_boolean_period(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    expense = alice.post(
        "/api/expenses",
        headers=ah,
        json={"title": "验证", "amount_cents": 1, "next_due": "2027-01-01"},
    ).json()
    result = alice.patch(f"/api/expenses/{expense['id']}", headers=ah, json={"period_months": True})
    assert result.status_code == 422


def test_concurrent_progression_is_not_lost(accounts):
    from concurrent.futures import ThreadPoolExecutor

    app, admin, headers, alice, ah, bob, bh = accounts
    expense = alice.post(
        "/api/expenses", headers=ah, json={"title": "并发", "amount_cents": 1, "next_due": "2027-01-31"}
    ).json()
    path = f"/api/expenses/{expense['id']}"

    def pay(_):
        with app.state.session_factory() as db:
            from app.models import Expense

            item = db.get(Expense, expense["id"])
            from app.records import advance_expense_due

            advance_expense_due(item)
            db.commit()

    with __import__("concurrent.futures").futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(pay, range(2)))
    latest = alice.get(path).json()
    assert latest["next_due"] in {"2027-02-28", "2027-03-31"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("progress", 2**63),
        ("total", 2**63),
        ("progress", 1_000_001),
        ("total", 1_000_001),
    ],
)
def test_show_episode_counts_have_explicit_storage_safe_bound(accounts, field, value):
    app, admin, headers, alice, ah, bob, bh = accounts
    result = alice.post("/api/shows", headers=ah, json={"title": "集数边界", field: value})
    assert result.status_code == 422
    show = alice.post("/api/shows", headers=ah, json={"title": "可编辑"}).json()
    result = alice.patch(f"/api/shows/{show['id']}", headers=ah, json={field: value})
    assert result.status_code == 422


def test_show_without_total_cannot_advance_beyond_episode_limit(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    show = alice.post(
        "/api/shows", headers=ah, json={"title": "上界", "progress": 1_000_000}
    ).json()
    path = f"/api/shows/{show['id']}"
    result = alice.post(path + "/advance", headers=ah)
    assert result.status_code == 400
    assert alice.get(path).json()["progress"] == 1_000_000
    alice.patch(path, headers=ah, json={"total": 1_000_000})
    assert alice.post(path + "/advance", headers=ah).status_code == 200


@pytest.mark.parametrize("collection", ["tasks", "expenses", "shows", "milestones"])
def test_out_of_range_record_ids_are_rejected_without_database_overflow(accounts, collection):
    app, admin, headers, alice, ah, bob, bh = accounts
    path = f"/api/{collection}/{2**63}"
    assert alice.get(path).status_code in (404, 422)
    assert alice.patch(path, headers=ah, json={"title": "invalid"}).status_code in (404, 422)
    assert alice.delete(path, headers=ah).status_code in (404, 422)
    if collection in ("expenses", "shows"):
        action = "pay" if collection == "expenses" else "advance"
        assert alice.post(path + "/" + action, headers=ah).status_code in (404, 422)
