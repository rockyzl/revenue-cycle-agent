import time
from dataclasses import asdict

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.fast_api_app import app
from app.portal import api, auth
from app.portal.agent import build_tools, validate_draft
from app.portal.fixtures import BILLS, seed, grant_key
from app.portal.service import Principal, digest, resolve_identity
from app.portal.store import SQLiteStore, get_store

ISSUER = 'https://securetoken.google.com/test-project'


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('PUBLIC_DEMO', 'false')
    monkeypatch.setenv('PORTAL_STORE', 'sqlite')
    monkeypatch.setenv('PORTAL_SQLITE_PATH', str(tmp_path/'db.sqlite'))
    monkeypatch.delenv('PORTAL_ORIGIN', raising=False)
    monkeypatch.setenv('MAESTRO_RELEASE_KEY', 'test-release')
    get_store.cache_clear()
    store = get_store(); seed(store, ISSUER)
    async def fake_auth(email, password):
        account = email.split('@')[0]
        if password != 'test':
            raise HTTPException(401, 'bad credentials')
        return {'iss': ISSUER, 'sub': 'rc-demo-'+account, 'exp': time.time()+3600}
    monkeypatch.setattr(auth, 'authenticate', fake_auth)
    async def start(*args):return {'job_key': 'test-job', 'state': 'Pending'}
    monkeypatch.setattr(api.uipath, 'start', start)
    yield store
    get_store.cache_clear()


def login(client, who):
    r = client.post('/portal/api/login', json={'email': who+'@demo.example', 'password': 'test'})
    assert r.status_code == 200
    client.headers['X-CSRF-Token'] = r.json()['csrf']


def send(client, bill='BILL-A100', key='request-1234567890'):
    return client.post('/portal/api/inquiries', json={'bill_id': bill, 'message': '为什么还要付钱？', 'request_id': key})


def test_identity_mapping_does_not_trust_email(setup):
    with pytest.raises(HTTPException):
        resolve_identity(setup, {'iss': 'https://attacker', 'sub': 'rc-demo-anna', 'email': 'anna@patient.demo.example'})
    with pytest.raises(HTTPException):
        resolve_identity(setup, {'iss': ISSUER, 'sub': 'unknown', 'email': 'anna@patient.demo.example'})


def test_account_bound_bills_and_proxy(setup):
    with TestClient(app) as c:
        assert c.get('/portal/api/bills').status_code == 401
        login(c, 'anna')
        assert {b['id'] for b in c.get('/portal/api/bills').json()['bills']} == {'BILL-A100','BILL-A101','BILL-C300'}
        denied=c.get('/portal/api/bills/BILL-B200')
        assert denied.status_code == 404
        assert denied.json() == c.get('/portal/api/bills/BILL-Z999').json()
        assert send(c,'BILL-B200').status_code == 404
        assert not setup.query('inquiries',{})


def test_revoke_grant_between_tool_calls(setup):
    p=Principal('anna',ISSUER,'rc-demo-anna')
    tools=build_tools(setup,p,'BILL-A100')
    assert tools[0]()['id']=='BILL-A100'
    setup.change('access_grants',grant_key('anna','patient-anna'),lambda x:{**x,'active':False})
    with pytest.raises(HTTPException):tools[1]()


def test_csrf_logout_and_role_boundaries(setup):
    with TestClient(app) as c:
        login(c,'anna')
        c.headers.pop('X-CSRF-Token')
        assert send(c).status_code==403
        login(c,'anna')
        assert c.post('/portal/api/logout',json={},headers={'Origin':'https://attacker.test'}).status_code==403
        assert c.post('/portal/api/inquiries/unknown/review',json={'decision':'approve','reply':'bad'}).status_code==403
        assert c.post('/portal/api/logout',json={}).status_code==200
        assert c.get('/portal/api/bills').status_code==401
        login(c,'reviewer')
        assert c.get('/portal/api/bills').status_code==403


def test_idempotent_intake_private_draft_and_callback(setup):
    with TestClient(app) as c:
        login(c,'anna'); r=send(c); assert r.status_code==200
        iid=r.json()['id']; assert send(c).json()['id']==iid
        assert send(c,bill='BILL-A101').status_code==409
        setup.change('inquiries',iid,lambda x:{**x,'draft':{'response':'private draft'},'status':'awaiting_review','worker_hash':digest('valid-worker')})
        assert 'draft' not in c.get('/portal/api/inquiries/'+iid).json()
        assert 'worker_hash' not in c.get('/portal/api/inquiries/'+iid).json()
        finish='/portal/api/worker/'+iid+'/finish'; body={'decision':'approve','reply':'Reviewed reply'}
        assert c.post(finish,json=body).status_code==401
        login(c,'ben')
        assert c.get('/portal/api/inquiries/'+iid).status_code==404
        login(c,'reviewer')
        assert c.get('/portal/api/inquiries/'+iid).json()['draft']['response']=='private draft'
        r=c.post(finish,json=body,headers={'Authorization':'Bearer valid-worker'})
        assert r.status_code==200
        assert c.post(finish,json=body,headers={'Authorization':'Bearer valid-worker'}).status_code==200
        assert c.post(finish,json={'decision':'reject','reply':'no'},headers={'Authorization':'Bearer valid-worker'}).status_code==409
        login(c,'anna')
        assert c.get('/portal/api/inquiries/'+iid).json()['response']=='Reviewed reply'


def test_callback_denied_after_proxy_revocation(setup):
    with TestClient(app) as c:
        login(c,'anna'); iid=send(c,'BILL-C300').json()['id']
        setup.change('inquiries',iid,lambda x:{**x,'status':'awaiting_review','worker_hash':digest('valid-worker')})
        setup.change('access_grants',grant_key('anna','patient-child'),lambda x:{**x,'active':False})
        r=c.post('/portal/api/worker/'+iid+'/finish',json={'decision':'approve','reply':'no'},headers={'Authorization':'Bearer valid-worker'})
        assert r.status_code==404
        assert setup.get('inquiries',iid)['status']=='awaiting_review'


def test_unverified_amounts_fail_closed():
    bill=BILLS[0]
    trace=[{'output':{'source_id':'demo-bill:BILL-A100'}},{'output':{'source_id':'demo-events:BILL-A100'}}]
    draft={'response':'Please pay $9999.00','evidence_ids':['demo-bill:BILL-A100','demo-events:BILL-A100'],'needs_specialist':False}
    d,checks=validate_draft(draft,trace,bill)
    assert not checks['quoted_amounts_match']
    assert '$9999' not in d['response'] and d['needs_specialist']


@pytest.mark.asyncio
async def test_task_lookup_binds_modern_folder_task_to_job(monkeypatch):
    from app.portal import uipath
    calls = []
    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith('GetTasksAcrossFolders'):
            return {'value': [{'Id': 7, 'Title': 'RC abc', 'CreatorJobKey': 'other-job'}, {'Id': 8, 'Title': 'RC abc', 'CreatorJobKey': 'our-job'}]}
        if path.endswith('GetTaskDataById'):
            assert kwargs['params']['taskId'] == 8
            return {'id': 8, 'title': 'RC abc', 'creatorJobKey': 'our-job', 'status': 0}
        return {}
    monkeypatch.setattr(uipath, 'request', request)
    assert await uipath.complete_task('abc', 'our-job', 'reject', 'Needs investigation') == 8
    assert calls[-1][2]['json']['action'] == 'Reject'
    assert await uipath.find_task('abc', 'missing-job') is None


def test_review_waits_for_maestro_callback(setup, monkeypatch):
    async def complete(iid, job, decision, reply):
        assert job == 'test-job' and decision == 'approve'
        return 8
    monkeypatch.setattr(api.uipath, 'complete_task', complete)
    with TestClient(app) as c:
        login(c, 'anna'); iid = send(c).json()['id']
        setup.change('inquiries', iid, lambda x: {**x, 'status': 'awaiting_review'})
        login(c, 'reviewer')
        r = c.post('/portal/api/inquiries/'+iid+'/review', json={'decision': 'approve', 'reply': 'Approved text'})
        assert r.status_code == 200 and r.json()['task_id'] == 8
        login(c, 'anna')
        assert c.get('/portal/api/inquiries/'+iid).json()['response'] is None
