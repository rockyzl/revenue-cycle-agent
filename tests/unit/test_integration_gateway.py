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


def test_expired_demo_blocks_reads_and_writes_before_tokens_or_charges(monkeypatch):
    monkeypatch.setenv('INTEGRATION_CLOSES_AT', '2001-01-01T00:00:00Z')
    monkeypatch.setattr(gateway, 'gateway_token', lambda: pytest.fail('No cloud token after closure'))
    monkeypatch.setattr(gateway, 'reserve_budget', lambda *args: pytest.fail('No spending reservation after closure'))
    state = client.get('/integration/api/availability')
    assert state.status_code == 200
    assert state.headers['cache-control'] == 'no-store'
    assert state.json()['available'] is False
    assert state.json()['code'] == 'demo_paused'
    for response in [client.get('/integration/api/status'), client.post('/integration/api/cases', json={})]:
        assert response.status_code == 503
        assert response.json()['detail']['code'] == 'demo_paused'
    assert client.get('/integration/api/arbitrary').status_code == 404


def test_future_demo_window_is_available(monkeypatch):
    monkeypatch.setenv('INTEGRATION_CLOSES_AT', '2099-01-01T00:00:00Z')
    assert client.get('/integration/api/availability').json() == {
        'available': True, 'closes_at': '2099-01-01T00:00:00Z'}


@pytest.mark.parametrize('deadline', ['not-a-date', '2026-11-23T00:00:00'])
def test_invalid_deadline_fails_closed(monkeypatch, deadline):
    monkeypatch.setenv('INTEGRATION_CLOSES_AT', deadline)
    assert client.get('/integration/api/status').status_code == 503
    assert client.get('/integration/api/availability').json()['available'] is False
