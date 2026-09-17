import httpx

from app import metadata as metadata_module


def response(method, url, payload):
    return httpx.Response(200, json=payload, request=httpx.Request(method, url))


def test_bangumi_metadata_includes_release_year_and_source_url(monkeypatch):
    payload = {
        "data": [
            {
                "id": 400602,
                "name": "Sousou no Frieren",
                "name_cn": "葬送的芙莉莲",
                "date": "2023-09-29",
                "eps": 28,
                "images": {},
            }
        ]
    }

    def fake_send(method, url, **kwargs):
        return response(method, url, payload)

    monkeypatch.setattr(metadata_module, "_send_resilient", fake_send)
    result = metadata_module.search_bangumi("芙莉莲", [2])[0]
    assert result["release_year"] == 2023
    assert result["source_url"] == "https://bgm.tv/subject/400602"


def test_tmdb_tv_metadata_includes_release_year_and_source_url(monkeypatch):
    search_payload = {
        "results": [
            {
                "id": 94997,
                "name": "漫长的季节",
                "first_air_date": "2023-04-22",
                "poster_path": None,
            }
        ]
    }

    def fake_send(method, url, **kwargs):
        if "/search/" in url:
            return response(method, url, search_payload)
        return response(
            method,
            url,
            {"number_of_episodes": 12, "number_of_seasons": 1, "status": "Ended"},
        )

    monkeypatch.setattr(metadata_module, "_send_resilient", fake_send)
    result = metadata_module.search_tmdb("漫长的季节", "tv", "test-key")[0]
    assert result["release_year"] == 2023
    assert result["source_url"] == "https://www.themoviedb.org/tv/94997"


def test_tmdb_movie_metadata_uses_movie_source_url(monkeypatch):
    search_payload = {
        "results": [
            {
                "id": 42,
                "title": "测试电影",
                "release_date": "2024-05-01",
                "poster_path": None,
            }
        ]
    }

    def fake_send(method, url, **kwargs):
        if "/search/" in url:
            return response(method, url, search_payload)
        return response(method, url, {"status": "Released"})

    monkeypatch.setattr(metadata_module, "_send_resilient", fake_send)
    result = metadata_module.search_tmdb("测试电影", "movie", "test-key")[0]
    assert result["release_year"] == 2024
    assert result["source_url"] == "https://www.themoviedb.org/movie/42"


def test_metadata_release_year_is_none_for_missing_or_malformed_dates(monkeypatch):
    payload = {
        "data": [
            {"id": 1, "name": "无日期", "date": None, "images": {}},
            {"id": 2, "name": "坏日期", "date": "not-a-date", "images": {}},
        ]
    }

    def fake_send(method, url, **kwargs):
        return response(method, url, payload)

    monkeypatch.setattr(metadata_module, "_send_resilient", fake_send)
    results = metadata_module.search_bangumi("日期", [2])
    assert [item["release_year"] for item in results] == [None, None]
