from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PASSWORD = "correct horse battery staple"


def sign_in(client, username="admin", password=PASSWORD):
    result = client.post("/api/auth/login", json={"username": username, "password": password})
    assert result.status_code == 200, result.text
    return {"X-CSRF-Token": result.json()["csrf_token"]}


@pytest.fixture
def accounts(tmp_path):
    from app.cli import create_admin

    app = create_app(tmp_path)
    with ExitStack() as stack:
        admin = stack.enter_context(TestClient(app))
        create_admin(app.state.settings, "admin", PASSWORD)
        admin_csrf = sign_in(admin)
        for name in ("alice", "bob"):
            response = admin.post(
                "/api/admin/users",
                json={
                    "username": name,
                    "password": PASSWORD,
                    "display_name": name,
                },
                headers=admin_csrf,
            )
            assert response.status_code == 201, response.text
        alice = stack.enter_context(TestClient(app))
        bob = stack.enter_context(TestClient(app))
        yield app, admin, admin_csrf, alice, sign_in(alice, "alice"), bob, sign_in(bob, "bob")


def test_login_cookie_and_csrf(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    assert alice.get("/api/auth/session").json()["user"]["username"] == "alice"
    assert alice.post("/api/tasks", json={"title": "unsafe"}).status_code == 403
    assert alice.post("/api/tasks", json={"title": "unsafe"}, headers=headers).status_code == 403
    assert (
        alice.post(
            "/api/tasks",
            json={"title": "unsafe"},
            headers={
                **ah,
                "Origin": "https://attacker.example",
            },
        ).status_code
        == 403
    )
    assert (
        alice.post(
            "/api/auth/login",
            json={"username": "alice", "password": PASSWORD},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert (
        bob.post("/api/auth/login", json={"username": "bob", "password": "wrong"}).status_code
        == 401
    )
    assert alice.get("/api/auth/session").headers["cache-control"] == "no-store"
    login = alice.post("/api/auth/login", json={"username": "alice", "password": PASSWORD})
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    csrf = {"X-CSRF-Token": login.json()["csrf_token"]}
    old_cookie = alice.cookies.get("digital_life_session")
    assert alice.post("/api/auth/logout", headers=csrf).status_code == 204
    alice.cookies.set("digital_life_session", old_cookie)
    assert alice.get("/api/auth/session").status_code == 401


def test_admin_boundaries_and_revocation(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    assert alice.get("/api/admin/users").status_code == 403
    assert (
        alice.post(
            "/api/admin/users",
            headers=ah,
            json={
                "username": "mallory",
                "password": PASSWORD,
                "display_name": "Mallory",
            },
        ).status_code
        == 403
    )
    users = admin.get("/api/admin/users").json()
    alice_id = next(u["id"] for u in users if u["username"] == "alice")
    admin_id = next(u["id"] for u in users if u["username"] == "admin")
    assert (
        admin.patch(
            f"/api/admin/users/{admin_id}", headers=headers, json={"is_active": False}
        ).status_code
        == 400
    )
    assert (
        admin.patch(
            f"/api/admin/users/{alice_id}", headers=headers, json={"is_active": False}
        ).status_code
        == 200
    )
    assert alice.get("/api/auth/session").status_code == 401
    assert (
        alice.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        admin.patch(
            f"/api/admin/users/{alice_id}",
            headers=headers,
            json={"is_active": True, "password": "replacement password"},
        ).status_code
        == 200
    )
    sign_in(alice, "alice", "replacement password")
    assert (
        admin.patch(
            f"/api/admin/users/{alice_id}",
            headers=headers,
            json={"password": "another replacement"},
        ).status_code
        == 200
    )
    assert alice.get("/api/auth/session").status_code == 401


def test_profile_password_and_extra_fields(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    updated = alice.patch(
        "/api/auth/profile",
        headers=ah,
        json={
            "display_name": "爱丽丝",
            "birthday": "2000-02-29",
            "timezone": "UTC",
            "theme": "dark",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["birthday"] == "2000-02-29"
    for body in (
        {"timezone": "Fake/Zone"},
        {"birthday": "2001-02-29"},
        {"is_admin": True},
        {"display_name": None},
        {"theme": "purple"},
    ):
        assert alice.patch("/api/auth/profile", headers=ah, json=body).status_code == 422
    assert (
        alice.post(
            "/api/auth/password",
            headers=ah,
            json={
                "current_password": "incorrect",
                "new_password": "new secure password",
            },
        ).status_code
        == 400
    )
    with TestClient(app) as other:
        sign_in(other, "alice")
        assert (
            alice.post(
                "/api/auth/password",
                headers=ah,
                json={
                    "current_password": PASSWORD,
                    "new_password": "new secure password",
                },
            ).status_code
            == 204
        )
        assert other.get("/api/auth/session").status_code == 401
    assert alice.get("/api/auth/session").status_code == 401
    sign_in(alice, "alice", "new secure password")


def test_expired_and_hashed_session(accounts):
    from sqlalchemy import select

    from app.models import LoginSession

    app, admin, headers, alice, ah, bob, bh = accounts
    token = alice.cookies.get("digital_life_session")
    with app.state.session_factory() as db:
        rows = db.scalars(select(LoginSession)).all()
        assert all(row.token_hash != token for row in rows)
        for row in rows:
            row.expires_at = 1
        db.commit()
    assert alice.get("/api/auth/session").status_code == 401


def test_unknown_username_and_malformed_tokens_are_denied(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    assert (
        alice.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": PASSWORD,
            },
        ).status_code
        == 401
    )
    assert (
        alice.post(
            "/api/tasks", json={"title": "blocked"}, headers={b"X-CSRF-Token": b"caf\xe9"}
        ).status_code
        == 403
    )
    alice.cookies.clear()
    alice.cookies.set("digital_life_session", "forged")
    assert alice.get("/api/auth/session").status_code == 401


def test_out_of_range_admin_user_id_is_rejected(accounts):
    app, admin, headers, alice, ah, bob, bh = accounts
    result = admin.patch(
        f"/api/admin/users/{2**63}", headers=headers, json={"display_name": "invalid"}
    )
    assert result.status_code in (404, 422)


@pytest.mark.parametrize("timezone", ["Factory", "localtime", "posix/UTC", "right/UTC"])
def test_profile_rejects_nonportable_system_timezones(accounts, timezone):
    app, admin, headers, alice, ah, bob, bh = accounts
    response = alice.patch("/api/auth/profile", headers=ah, json={"timezone": timezone})
    assert response.status_code == 422
    assert alice.get("/api/auth/session").json()["user"]["timezone"] == "Asia/Shanghai"


@pytest.mark.parametrize("timezone", ["UTC", "GMT", "Asia/Shanghai", "America/New_York"])
def test_profile_accepts_portable_timezones(accounts, timezone):
    app, admin, headers, alice, ah, bob, bh = accounts
    response = alice.patch("/api/auth/profile", headers=ah, json={"timezone": timezone})
    assert response.status_code == 200
    assert response.json()["timezone"] == timezone


def test_legacy_system_timezone_does_not_block_login_or_profile_repair(accounts):
    from sqlalchemy import select

    from app.models import User

    app, admin, headers, alice, ah, bob, bh = accounts
    with app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.username == "alice"))
        user.timezone = "Factory"
        db.commit()
    assert alice.get("/api/auth/session").status_code == 200
    assert alice.get("/api/export").status_code == 200
    csrf = sign_in(alice, "alice")
    response = alice.patch("/api/auth/profile", headers=csrf, json={"timezone": "UTC"})
    assert response.status_code == 200
    assert response.json()["timezone"] == "UTC"
