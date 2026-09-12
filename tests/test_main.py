from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status":"ok"}

def test_read_expenses():
    response = client.get("/expenses")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body,list)
    assert body[0]["description"] == "Coffee"