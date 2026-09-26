import pytest
from test_auth import sign_in  # noqa: F401

from app.bookmarks.service import blocked_host


def test_bookmark_crud_and_isolation(accounts):
    _, _, _, alice, headers, bob, bob_headers = accounts
    created = alice.post(
        "/api/bookmarks",
        json={"url": "https://example.com/docs", "title": "文档", "folder": "工作"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    bookmark = created.json()
    assert bookmark["folder"] == "工作"
    assert bookmark["visit_count"] == 0
    assert bookmark["last_visited_at"] is None

    updated = alice.patch(
        f"/api/bookmarks/{bookmark['id']}",
        json={"title": "团队文档", "note": "需内网", "starred": True},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "团队文档"
    assert updated.json()["url"] == "https://example.com/docs"
    assert updated.json()["starred"] is True

    # Ownership: another account must not see, edit or delete the row.
    assert bob.get(f"/api/bookmarks/{bookmark['id']}", headers=bob_headers).status_code == 404
    assert (
        bob.patch(
            f"/api/bookmarks/{bookmark['id']}", json={"title": "x"}, headers=bob_headers
        ).status_code
        == 404
    )
    assert (
        bob.post(f"/api/bookmarks/{bookmark['id']}/visit", headers=bob_headers).status_code == 404
    )
    assert bob.delete(f"/api/bookmarks/{bookmark['id']}", headers=bob_headers).status_code == 404
    assert alice.get("/api/bookmarks", headers=headers).json()[0]["title"] == "团队文档"
    assert bob.get("/api/bookmarks", headers=bob_headers).json() == []

    assert alice.delete(f"/api/bookmarks/{bookmark['id']}", headers=headers).status_code == 204
    assert alice.get("/api/bookmarks", headers=headers).json() == []


def test_bookmark_url_validation(accounts):
    _, _, _, alice, headers, _, _ = accounts
    for url in (
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "ftp://example.com/file",
        "example.com",
        "http://",
        "http:// /example.com",
        "https://example.com/" + "a" * 2100,
        "",
    ):
        response = alice.post("/api/bookmarks", json={"url": url, "title": "x"}, headers=headers)
        assert response.status_code == 422, (url, response.status_code)
    assert (
        alice.post("/api/bookmarks", json={"title": "缺网址"}, headers=headers).status_code == 422
    )
    assert (
        alice.post(
            "/api/bookmarks",
            json={"url": "https://example.com", "title": "x" * 161},
            headers=headers,
        ).status_code
        == 422
    )
    # A query string with spaces is normalised rather than rejected.
    ok = alice.post(
        "/api/bookmarks",
        json={"url": " https://example.com/a?b=c ", "title": "带空格的网址"},
        headers=headers,
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["url"] == "https://example.com/a?b=c"


def test_bookmark_search_folder_filter_and_starred_order(accounts):
    _, _, _, alice, headers, _, _ = accounts
    for payload in (
        {"url": "https://a.example.com", "title": "服务器面板", "folder": "运维", "starred": True},
        {"url": "https://b.example.com", "title": "文档中心", "folder": "工作", "note": "内网"},
        {"url": "https://c.example.com", "title": "未分组站点"},
    ):
        assert alice.post("/api/bookmarks", json=payload, headers=headers).status_code == 201

    listed = alice.get("/api/bookmarks", headers=headers).json()
    assert [row["title"] for row in listed] == ["服务器面板", "未分组站点", "文档中心"]

    assert [
        row["title"] for row in alice.get("/api/bookmarks?folder=运维", headers=headers).json()
    ] == ["服务器面板"]
    # An empty folder selects only ungrouped rows.
    assert [
        row["title"] for row in alice.get("/api/bookmarks?folder=", headers=headers).json()
    ] == ["未分组站点"]
    assert [
        row["title"] for row in alice.get("/api/bookmarks?q=example.com", headers=headers).json()
    ] == ["服务器面板", "未分组站点", "文档中心"]
    assert [row["title"] for row in alice.get("/api/bookmarks?q=内网", headers=headers).json()] == [
        "文档中心"
    ]
    assert alice.get("/api/bookmarks?q=不存在的关键词", headers=headers).json() == []


def test_bookmark_visit_count(accounts):
    _, _, _, alice, headers, _, _ = accounts
    created = alice.post(
        "/api/bookmarks", json={"url": "https://example.com", "title": "示例"}, headers=headers
    )
    bookmark = created.json()
    first = alice.post(f"/api/bookmarks/{bookmark['id']}/visit", headers=headers).json()
    assert first["visit_count"] == 1
    assert first["last_visited_at"] is not None
    second = alice.post(f"/api/bookmarks/{bookmark['id']}/visit", headers=headers).json()
    assert second["visit_count"] == 2
    # Visiting never rewrites the editable fields.
    assert second["title"] == "示例"
    assert second["url"] == "https://example.com"


def test_bookmark_export_import_round_trip(accounts):
    _, _, _, alice, headers, _, _ = accounts
    alice.post(
        "/api/bookmarks",
        json={"url": "https://a.example.com", "title": "面板", "folder": "运维"},
        headers=headers,
    )
    visited = alice.post(
        "/api/bookmarks", json={"url": "https://b.example.com", "title": "文档"}, headers=headers
    ).json()
    alice.post(f"/api/bookmarks/{visited['id']}/visit", headers=headers)

    export = alice.get("/api/export", headers=headers).json()
    assert [row["title"] for row in export["bookmarks"]] == ["面板", "文档"]
    assert export["bookmarks"][1]["visit_count"] == 1
    assert export["bookmarks"][1]["last_visited_at"] is not None

    result = alice.post("/api/import", json=export, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["imported"]["bookmarks"] == 2
    # The list is ordered starred first, then newest id first.
    restored = alice.get("/api/bookmarks", headers=headers).json()
    assert [row["title"] for row in restored] == ["文档", "面板"]
    assert restored[0]["visit_count"] == 1
    assert restored[0]["last_visited_at"] is not None
    assert restored[0]["folder"] is None
    assert restored[1]["folder"] == "运维"

    # An export written before bookmarks existed carries no such key; importing
    # it still clears the table, so no stale rows survive a restore.
    legacy = {
        "user": export["user"],
        "tasks": [{"title": "占位待办"}],
        "expenses": [],
        "shows": [],
        "milestones": [],
        "notes": [],
        "projects": [],
    }
    restored_export = alice.post("/api/import", json=legacy, headers=headers)
    assert restored_export.status_code == 200, restored_export.text
    assert restored_export.json()["imported"]["bookmarks"] == 0
    assert alice.get("/api/bookmarks", headers=headers).json() == []


def test_bookmark_import_rejects_bad_rows(accounts):
    _, _, _, alice, headers, _, _ = accounts
    export = alice.get("/api/export", headers=headers).json()
    bad = {**export, "bookmarks": [{"url": "javascript:alert(1)", "title": "x"}]}
    response = alice.post("/api/import", json=bad, headers=headers)
    assert response.status_code == 422, response.text
    assert "bookmarks" in response.json()["detail"]


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "localhost", "10.0.0.5", "192.168.66.90", "172.16.0.1", "169.254.1.1", "::1"],
)
def test_private_hosts_are_blocked(host):
    assert blocked_host(host) is True


@pytest.mark.parametrize("host", ["example.com", "93.184.216.34"])
def test_public_hosts_are_allowed(host):
    # Resolving a real name would need the network; the check still accepts it
    # only when the name is not a literal private address.
    assert blocked_host(host) is False


def test_title_lookup_refuses_private_targets(accounts):
    _, _, _, alice, headers, _, _ = accounts
    for url in ("http://127.0.0.1/x", "http://localhost/x", "http://192.168.66.90/"):
        response = alice.post("/api/bookmarks/title", json={"url": url}, headers=headers)
        assert response.status_code == 422, (url, response.text)
        assert "内网" in response.json()["detail"]
    assert (
        alice.post(
            "/api/bookmarks/title", json={"url": "javascript:alert(1)"}, headers=headers
        ).status_code
        == 422
    )


def test_title_lookup_disabled_by_env(accounts):
    from dataclasses import replace

    app, _, _, alice, headers, _, _ = accounts
    app.state.settings = replace(app.state.settings, metadata_disabled=True)
    response = alice.post(
        "/api/bookmarks/title", json={"url": "https://example.com"}, headers=headers
    )
    assert response.status_code == 503, response.text
