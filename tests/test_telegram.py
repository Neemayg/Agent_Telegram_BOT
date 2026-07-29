from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_run_log_exists():
    # Make sure logs dir exists and is cleaned
    settings.setup_directories()
    # Trigger get log
    response = client.get("/run.jsonl")
    assert response.status_code == 200
    # The return content should be text/jsonlines
    assert "runs.jsonl" in response.headers.get("content-disposition", "")


def test_telegram_webhook_invalid_payload():
    # Sending invalid data to webhook should fail gracefully (e.g. 500 or validation status code)
    response = client.post("/telegram-webhook", content="invalid-json")
    # Should not crash the server and return a failure code
    assert response.status_code in [400, 500, 503]
