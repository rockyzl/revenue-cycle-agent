import pytest
from fastapi.testclient import TestClient

from app.fast_api_app import app


def test_ui_and_review_contract():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").json()["mode"] == "replay"
        r = client.post(
            "/demo/run",
            json={"message": "Duplicate charge; please review", "bill_id": "DEMO-1001"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["paused"] and data["triage"]["needs_specialist"]
        path = f"/demo/{data['session_id']}/review"
        assert (
            client.post(path, json={"decision": "approve", "send": True}).status_code
            == 422
        )
        done = client.post(path, json={"decision": "reject"})
        assert done.json()["status"] == "rejected"
        assert client.post(path, json={"decision": "approve"}).status_code == 409
        assert (
            client.post(
                "/demo/not-a-session/review", json={"decision": "approve"}
            ).status_code
            == 404
        )


@pytest.mark.parametrize(
    "body",
    [
        {"message": "", "bill_id": "DEMO-1001"},
        {"message": "x", "bill_id": "REAL-ACCOUNT"},
        {"message": "x" * 2001, "bill_id": "DEMO-1001"},
    ],
)
def test_input_contract(body):
    with TestClient(app) as client:
        assert client.post("/demo/run", json=body).status_code == 422
