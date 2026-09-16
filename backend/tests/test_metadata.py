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
