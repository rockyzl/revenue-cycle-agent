from fastapi.testclient import TestClient

from app.fast_api_app import app


def test_public_demo_rejects_arbitrary_model_input(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO", "true")
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/assets/workbench.js").status_code == 200
        assert len(client.get("/api/config").json()["cases"]) == 6
        assert (
            client.post(
                "/api/investigate", json={"case_id": "explain", "question": "arbitrary"}
            ).status_code
            == 422
        )
        assert (
            client.post("/api/investigate", json={"case_id": "unknown"}).status_code
            == 422
        )
        assert (
            client.post(
                "/demo/run", json={"message": "hello", "bill_id": "DEMO-1001"}
            ).status_code
            == 404
        )


def test_cost_review_requires_a_valid_session():
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/sessions/missing/review", json={"decision": "approve"}
            ).status_code
            == 404
        )
