import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import integration_api as gateway

app = FastAPI()
app.include_router(gateway.router)
client = TestClient(app)


def test_gateway_is_bounded_and_rejects_cross_origin_mutation(monkeypatch):
    monkeypatch.setenv('INTEGRATION_BACKEND_URL', 'http://10.128.0.2:8780')
    monkeypatch.setenv('PORTAL_ORIGIN', 'https://demo.example')
    assert client.get('/integration/api/arbitrary').status_code == 404
    assert client.get('/integration/api/records/not-a-key').status_code == 404
    assert client.post('/integration/api/import/fixture', headers={'Origin': 'https://elsewhere.example', 'X-Lab-Request': 'demo'}, json={}).status_code == 403
    assert client.post('/integration/api/import/fixture', json={}).status_code == 403
    assert client.post('/integration/api/cases', headers={'X-Lab-Request': 'demo'}, content='x' * 8200).status_code == 413


def test_unconfigured_cloud_lab_is_explicit(monkeypatch):
    monkeypatch.delenv('INTEGRATION_BACKEND_URL', raising=False)
    assert client.get('/integration/api/status').status_code == 503
