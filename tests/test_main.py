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


def test_cors_preflight_allows_delete_from_frontend_origin():
    # A browser sends this OPTIONS "preflight" before a cross-origin DELETE;
    # if it is rejected, the browser never sends the real DELETE.
    response = client.options(
        "/expenses/1",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_cors_preflight_allows_authorization_header():
    # Every real request from the frontend carries an `Authorization: Bearer
    # ...` header (see frontend/src/api.ts), so the browser's preflight asks
    # for permission to send it. TestClient's normal requests don't send an
    # Origin header, so this preflight case is the one the plain request
    # tests above can't catch.
    response = client.options(
        "/expenses",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers


def test_cors_preflight_allows_the_deployed_frontend_origin():
    # The frontend is also deployed and reachable on the public internet
    # (Issue #42); the deployed site's own origin needs the same preflight
    # access as localhost does during development.
    response = client.options(
        "/expenses",
        headers={
            "Origin": "https://expense-classifier-1.onrender.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://expense-classifier-1.onrender.com"
    )

