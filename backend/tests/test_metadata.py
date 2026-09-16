import httpx
import pytest
from fastapi.testclient import TestClient

from app import metadata as metadata_module
from app.main import create_app


@pytest.fixture
def workspace(tmp_path):
    from app.cli import create_admin

    app = create_app(tmp_path)
    with TestClient(app) as client:
        create_admin(app.state.settings, "admin", "correct horse battery staple")
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "correct horse battery staple"},
        )
        assert login.status_code == 200
        yield client, {"X-CSRF-Token": login.json()["csrf_token"]}, app


def stub_bangumi(monkeypatch, payload=None, error=None):
    calls = {}

    def fake(keyword, subject_types):
        calls["keyword"] = keyword
        calls["subject_types"] = subject_types
        if error:
            raise error
        return payload if payload is not None else []

    monkeypatch.setattr(metadata_module, "search_bangumi", fake)
    return calls


def test_metadata_requires_authentication(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/api/shows/metadata", params={"keyword": "芙莉莲"})
        assert response.status_code == 401


def test_metadata_validates_input(workspace):
    client, headers, _ = workspace
    bad_type = client.get(
        "/api/shows/metadata", params={"keyword": "x", "media_type": "variety"}, headers=headers
    )
    assert bad_type.status_code == 400
    blank = client.get("/api/shows/metadata", params={"keyword": "  "}, headers=headers)
    assert blank.status_code == 422
    too_long = client.get("/api/shows/metadata", params={"keyword": "长" * 81}, headers=headers)
    assert too_long.status_code == 422


def test_metadata_returns_normalized_results(workspace, monkeypatch):
    client, headers, _ = workspace
    calls = stub_bangumi(
        monkeypatch,
        payload=[
            {
                "source": "bangumi",
                "source_id": 400602,
                "title": "葬送的芙莉莲",
                "original_title": "葬送のフリーレン",
                "air_date": "2023-09-29",
                "total_episodes": 28,
            }
        ],
    )
    response = client.get("/api/shows/metadata", params={"keyword": " 芙莉莲 "}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["title"] == "葬送的芙莉莲"
    assert calls["keyword"] == "芙莉莲"
    assert calls["subject_types"] == [2]


def test_metadata_maps_upstream_failures_to_502(workspace, monkeypatch):
    client, headers, _ = workspace
    stub_bangumi(monkeypatch, error=httpx.ConnectError("offline"))
    response = client.get("/api/shows/metadata", params={"keyword": "芙莉莲"}, headers=headers)
    assert response.status_code == 502
    assert "Bangumi" in response.json()["detail"]


def test_metadata_can_be_disabled_by_operator(workspace, monkeypatch):
    client, headers, app = workspace
    calls = stub_bangumi(monkeypatch, payload=[])
    object.__setattr__(app.state.settings, "metadata_disabled", True)
    response = client.get("/api/shows/metadata", params={"keyword": "芙莉莲"}, headers=headers)
    assert response.status_code == 503
    assert "keyword" not in calls


def test_metadata_supports_real_person_shows(workspace, monkeypatch):
    client, headers, _ = workspace
    calls = stub_bangumi(
        monkeypatch,
        payload=[
            {
                "source": "bangumi",
                "source_id": 396646,
                "title": "漫长的季节",
                "original_title": "漫长的季节",
                "air_date": "2023-04-22",
                "total_episodes": 12,
                "platform": "华语剧",
            }
        ],
    )
    response = client.get(
        "/api/shows/metadata", params={"keyword": "漫长的季节", "media_type": "tv"}, headers=headers
    )
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["platform"] == "华语剧"
    assert calls["subject_types"] == [6]


def stub_tmdb(monkeypatch, payload=None):
    calls = {}

    def fake(keyword, kind, api_key):
        calls.update({"keyword": keyword, "kind": kind, "api_key": api_key})
        return payload if payload is not None else []

    monkeypatch.setattr(metadata_module, "search_tmdb", fake)
    return calls


def test_metadata_source_is_an_explicit_choice(workspace, monkeypatch):
    client, headers, app = workspace
    object.__setattr__(app.state.settings, "tmdb_api_key", "test-key")
    tmdb_calls = stub_tmdb(
        monkeypatch,
        payload=[
            {
                "source": "tmdb",
                "source_id": 94997,
                "title": "漫长的季节",
                "original_title": "The Long Season",
                "air_date": "2023-04-22",
                "total_episodes": 12,
                "platform": None,
                "image": "https://image.tmdb.org/t/p/w342/abc.jpg",
                "seasons": 1,
                "air_status": "ended",
            }
        ],
    )
    drama = client.get(
        "/api/shows/metadata",
        params={"keyword": "漫长的季节", "media_type": "tv", "source": "tmdb"},
        headers=headers,
    )
    assert drama.status_code == 200, drama.text
    assert drama.json()["results"][0]["seasons"] == 1
    assert drama.json()["results"][0]["air_status"] == "ended"
    assert tmdb_calls["kind"] == "tv" and tmdb_calls["api_key"] == "test-key"
    # TMDB also serves animation through its TV catalogue.
    anime = client.get(
        "/api/shows/metadata",
        params={"keyword": "芙莉莲", "media_type": "anime", "source": "tmdb"},
        headers=headers,
    )
    assert anime.status_code == 200
    assert tmdb_calls["kind"] == "tv"


def test_metadata_tmdb_requires_configured_key(workspace, monkeypatch):
    client, headers, _ = workspace
    stub_tmdb(monkeypatch)
    missing_key = client.get(
        "/api/shows/metadata",
        params={"keyword": "漫长的季节", "media_type": "tv", "source": "tmdb"},
        headers=headers,
    )
    assert missing_key.status_code == 400
    assert "TMDB_API_KEY" in missing_key.json()["detail"]
    unknown = client.get(
        "/api/shows/metadata",
        params={"keyword": "x", "media_type": "tv", "source": "douban"},
        headers=headers,
    )
    assert unknown.status_code == 400


def test_metadata_bangumi_serves_every_media_type(workspace, monkeypatch):
    client, headers, _ = workspace
    calls = stub_bangumi(monkeypatch, payload=[])
    for media_type, subject_types in (("anime", [2]), ("tv", [6]), ("movie", [6])):
        response = client.get(
            "/api/shows/metadata",
            params={"keyword": "漫长的季节", "media_type": media_type, "source": "bangumi"},
            headers=headers,
        )
        assert response.status_code == 200
        assert calls["subject_types"] == subject_types


def stub_image(monkeypatch, content=b"poster-bytes", content_type="image/jpeg", fail=None):
    calls = {"count": 0}

    def fake(url):
        calls["count"] += 1
        calls["url"] = url
        if fail:
            raise fail
        return content, content_type

    monkeypatch.setattr(metadata_module, "fetch_image", fake)
    return calls


def test_show_poster_is_fetched_cached_and_session_scoped(workspace, monkeypatch):
    client, headers, app = workspace
    calls = stub_image(monkeypatch)
    created = client.post(
        "/api/shows",
        json={
            "title": "漫长的季节",
            "media_type": "tv",
            "status": "watching",
            "source": "tmdb",
            "source_id": 94997,
            "poster_path": "https://image.tmdb.org/t/p/w342/abc.jpg",
            "seasons": 1,
            "air_status": "ended",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    show_id = created.json()["id"]
    first = client.get(f"/api/shows/{show_id}/poster", headers=headers)
    assert first.status_code == 200
    assert first.content == b"poster-bytes"
    assert first.headers["content-type"] == "image/jpeg"
    assert first.headers["cache-control"] == "private, max-age=604800"
    assert calls["count"] == 1
    second = client.get(f"/api/shows/{show_id}/poster", headers=headers)
    assert second.status_code == 200
    assert calls["count"] == 1  # served from the on-disk cache
    assert (app.state.settings.data_dir / "posters" / f"{show_id}.img").is_file()


def test_show_poster_rejects_missing_and_untrusted_sources(workspace, monkeypatch):
    client, headers, _ = workspace
    plain = client.post("/api/shows", json={"title": "无封面"}, headers=headers).json()
    missing = client.get(f"/api/shows/{plain['id']}/poster", headers=headers)
    assert missing.status_code == 404
    hostile = client.post(
        "/api/shows",
        json={"title": "恶意来源", "poster_path": "http://127.0.0.1:8000/api/tasks"},
        headers=headers,
    ).json()
    blocked = client.get(f"/api/shows/{hostile['id']}/poster", headers=headers)
    assert blocked.status_code == 400
    stub_image(monkeypatch, fail=httpx.ConnectError("down"))
    unreachable = client.post(
        "/api/shows",
        json={"title": "下载失败", "poster_path": "https://image.tmdb.org/t/p/w342/x.jpg"},
        headers=headers,
    ).json()
    degraded = client.get(f"/api/shows/{unreachable['id']}/poster", headers=headers)
    assert degraded.status_code == 502


def test_send_resilient_retries_ipv4_when_network_unreachable(monkeypatch):
    calls = []

    def fake_send(method, url, *, transport=None, **kwargs):
        calls.append(transport is not None)
        if transport is None:
            raise httpx.ConnectError("[Errno 101] Network is unreachable")
        return "ok"

    monkeypatch.setattr(metadata_module, "_send", fake_send)
    assert metadata_module._send_resilient("get", "https://api.themoviedb.org/3") == "ok"
    assert calls == [False, True]


def test_send_resilient_passes_other_connect_errors_through(monkeypatch):
    def fake_send(method, url, *, transport=None, **kwargs):
        raise httpx.ConnectError("[Errno -2] getaddrinfo failed")

    monkeypatch.setattr(metadata_module, "_send", fake_send)
    with pytest.raises(httpx.ConnectError):
        metadata_module._send_resilient("get", "https://api.bgm.tv")
