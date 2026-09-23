from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status":"ok"}


def test_cors_preflight_allows_json_post_from_frontend_origin():
    # A browser sends this OPTIONS "preflight" before a cross-origin POST with a
    # JSON body; if it is rejected, the browser never sends the real POST.
    response = client.options(
        "/expenses",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]

