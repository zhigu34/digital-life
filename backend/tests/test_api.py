from fastapi.testclient import TestClient

from app.main import create_app


def test_health_and_authentication_required(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        for path in ("tasks", "expenses", "shows", "milestones", "export", "auth/session"):
            assert client.get("/api/" + path).status_code == 401
