"""Patient inbox, staff worklist and narrowly scoped Maestro callbacks."""
import asyncio
import os
import secrets
import time
from dataclasses import asdict
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import agent, auth, uipath
from .fixtures import DEMO_ACCOUNTS
from .display import english_history
from .service import Principal, account_for, authorized_bill, list_bills, visible_inquiry, require_role, audit, digest
from .store import get_store, reserve_budget

router = APIRouter(prefix='/portal/api')


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(max_length=160)
    password: str = Field(max_length=160)


class Inquiry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bill_id: str = Field(pattern=r'^BILL-[A-Z][0-9]{3}$')
    message: str = Field(min_length=3, max_length=1200)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9-]{16,64}$')


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approve', 'reject']
    reply: str = Field(min_length=1, max_length=2200)


def public_row(row, role):
    safe = {k: row[k] for k in ('id', 'bill_id', 'message', 'status', 'created_at', 'updated_at')}
    safe['response'] = row.get('approved_response')
    safe['job_key'] = row.get('job_key')
    safe['workflow'] = 'UiPath Maestro Flow'
    if role == 'reviewer':
        safe.update({k: row.get(k) for k in ('draft', 'trace', 'checks', 'review', 'task_id', 'error')})
    return english_history(safe)


@router.get('/config')
def config():
    return {'accounts': [{k: a[k] for k in ('id', 'name', 'email', 'password', 'role')} for a in DEMO_ACCOUNTS], 'identity': 'Google Cloud Identity Platform', 'database': 'Cloud Firestore' if os.getenv('PORTAL_STORE') == 'firestore' else 'Local SQLite', 'maestro_configured': bool(os.getenv('MAESTRO_RELEASE_KEY')), 'data': 'Fictional patients, bills and insurance/payment events. CMS public aggregates are a separate reference demo.'}


@router.post('/login')
async def login(body: Login, request: Request, response: Response):
    auth.same_origin(request)
    auth.login_limit(request)
    claims = await auth.authenticate(body.email, body.password)
    token, csrf, principal = auth.create_session(get_store(), claims)
    response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True, secure=os.getenv('PUBLIC_DEMO') == 'true', samesite='strict', path='/')
    return {'account': account_for(get_store(), principal), 'csrf': csrf}


@router.get('/me')
def me(session=Depends(auth.require_session)):
    principal, row = session
    return {'account': account_for(get_store(), principal), 'csrf': row['csrf']}


@router.post('/logout')
def logout(request: Request, response: Response, session=Depends(auth.require_session)):
    get_store().delete('sessions', digest(request.cookies[auth.COOKIE]))
    response.delete_cookie(auth.COOKIE, path='/')
    return {'ok': True}


@router.get('/bills')
def bills(session=Depends(auth.require_session)):
    return {'bills': list_bills(get_store(), session[0])}


@router.get('/bills/{bill_id}')
def bill(bill_id: str, session=Depends(auth.require_session)):
    return authorized_bill(get_store(), session[0], bill_id)


@router.get('/inquiries')
def inquiries(session=Depends(auth.require_session)):
    store = get_store(); p = session[0]; account = account_for(store, p)
    field = 'reviewer_id' if account['role'] == 'reviewer' else 'account_id'
    result = []
    for row in store.query('inquiries', {field: p.account_id}):
        try:
            visible_inquiry(store, p, row['id'])
            result.append(public_row(row, account['role']))
        except HTTPException:
            continue
    return {'inquiries': sorted(result, key=lambda x: x['created_at'], reverse=True)}


@router.get('/inquiries/{inquiry_id}')
def inquiry(inquiry_id: str, session=Depends(auth.require_session)):
    store = get_store(); p = session[0]
    return public_row(visible_inquiry(store, p, inquiry_id), account_for(store, p)['role'])


@router.post('/inquiries')
async def create_inquiry(body: Inquiry, session=Depends(auth.require_session)):
    store = get_store(); p = session[0]
    bill = authorized_bill(store, p, body.bill_id)
    if not os.getenv('MAESTRO_RELEASE_KEY'):
        raise HTTPException(503, 'The workflow is being configured. New inquiries are not available yet.')
    key = digest(p.account_id + ':' + body.request_id)
    old = store.get('requests', key)
    if old:
        row = visible_inquiry(store, p, old['inquiry_id'])
        if row['bill_id'] != body.bill_id or row['message'] != body.message:
            raise HTTPException(409, 'This request ID has already been used for different content.')
        return public_row(row, 'patient')
    try:
        reserve_budget(store, 'inquiry-' + p.account_id, 12, 86400)
        reserve_budget(store, 'inquiry-global', 40, 86400)
    except ValueError as exc:
        raise HTTPException(429, 'The daily demo limit has been reached. Existing inquiries can still be viewed and reviewed.') from exc
    inquiry_id = uuid4().hex; worker_token = secrets.token_urlsafe(32); now = time.time()
    row = {'id': inquiry_id, 'bill_id': bill['id'], 'patient_id': bill['patient_id'], 'account_id': p.account_id, 'principal': asdict(p), 'reviewer_id': 'reviewer', 'message': body.message, 'status': 'starting', 'created_at': now, 'updated_at': now, 'worker_hash': digest(worker_token), 'worker_expires': now + 86400}
    # Atomic uniqueness claim prevents duplicate submissions from starting two jobs.
    try:
        store.create('requests', key, {'inquiry_id': inquiry_id})
    except Exception as exc:
        raise HTTPException(409, 'This request is being submitted. Please refresh shortly.') from exc
    store.create('inquiries', inquiry_id, row)
    try:
        job = await uipath.start(inquiry_id, worker_token)
        def started(current):
            return {**current, 'job_key': job['job_key'], 'status': 'queued' if current['status'] == 'starting' else current['status'], 'updated_at': time.time()}
        row = store.change('inquiries', inquiry_id, started)
    except Exception as exc:
        store.change('inquiries', inquiry_id, lambda x: {**x, 'status': 'failed', 'error': 'Maestro could not start. No reply was generated or sent.', 'updated_at': time.time()})
        raise HTTPException(502, 'Maestro could not start. Your inquiry has been saved.') from exc
    audit(store, p, 'submit_inquiry', inquiry_id, True)
    return public_row(row, 'patient')


@router.post('/inquiries/{inquiry_id}/review')
async def review(inquiry_id: str, body: Review, session=Depends(auth.require_session)):
    store = get_store(); p = session[0]
    require_role(store, p, 'reviewer')
    row = visible_inquiry(store, p, inquiry_id)
    if row['status'] != 'awaiting_review':
        raise HTTPException(409, 'This inquiry is not ready for review or has already been processed.')
    # Also re-check the patient's current grant before releasing any content.
    authorized_bill(store, Principal(**row['principal']), row['bill_id'])
    task_id = await uipath.complete_task(inquiry_id, row['job_key'], body.decision, body.reply)
    row = store.change('inquiries', inquiry_id, lambda x: {**x, 'task_id': task_id, 'review': {'reviewer_id': p.account_id, 'decision': body.decision, 'method': 'demo_reviewer_click_via_action_center_api', 'at': time.time()}, 'updated_at': time.time()})
    audit(store, p, 'review_' + body.decision, inquiry_id, True)
    return public_row(row, 'reviewer')  # Only Maestro callback can publish the reply.


def worker(request, inquiry_id):
    store = get_store(); row = store.get('inquiries', inquiry_id)
    token = request.headers.get('authorization', '').removeprefix('Bearer ')
    if not row or row.get('worker_expires', 0) < time.time() or not secrets.compare_digest(row.get('worker_hash', ''), digest(token)):
        raise HTTPException(401, 'Invalid workflow credential')
    p = Principal(**row['principal'])
    authorized_bill(store, p, row['bill_id'])
    return store, row, p


@router.post('/worker/{inquiry_id}/draft')
async def prepare_draft(inquiry_id: str, request: Request):
    store, row, p = worker(request, inquiry_id)
    if row.get('draft'):
        return {'reply': row['draft']['response'], 'evidence': json_evidence(row), 'message': row['message']}
    def claim(current):
        if current['status'] not in {'starting', 'queued'}:
            raise HTTPException(409, 'Draft already running or failed')
        return {**current, 'status': 'investigating', 'updated_at': time.time()}
    store.change('inquiries', inquiry_id, claim)
    try:
        result = await asyncio.wait_for(agent.investigate(store, p, row['bill_id'], row['message']), timeout=175)
        authorized_bill(store, p, row['bill_id'])
        row = store.change('inquiries', inquiry_id, lambda x: {**x, **{k: result[k] for k in ('draft', 'trace', 'checks')}, 'status': 'awaiting_review', 'updated_at': time.time()})
        return {'reply': row['draft']['response'], 'evidence': json_evidence(row), 'message': row['message']}
    except Exception as exc:
        store.change('inquiries', inquiry_id, lambda x: {**x, 'status': 'failed', 'error': 'The AI or access check failed. No publishable reply was generated.', 'updated_at': time.time()})
        raise HTTPException(502, 'Draft preparation failed') from exc


def json_evidence(row):
    import json
    return json.dumps({'bill_id': row['bill_id'], 'tools': row['trace'], 'checks': row['checks'], 'synthetic': True}, ensure_ascii=False)


@router.post('/worker/{inquiry_id}/finish')
def finish(inquiry_id: str, body: Review, request: Request):
    store, row, p = worker(request, inquiry_id)
    target = 'approved' if body.decision == 'approve' else 'rejected'
    def apply(current):
        if current['status'] == target:
            return current  # idempotent workflow delivery
        if current['status'] != 'awaiting_review':
            raise HTTPException(409, 'Invalid workflow transition')
        return {**current, 'status': target, 'approved_response': body.reply if target == 'approved' else None, 'updated_at': time.time(), 'completed_by': 'UiPath Maestro callback'}
    row = store.change('inquiries', inquiry_id, apply)
    audit(store, p, 'maestro_' + target, inquiry_id, True)
    return {'status': row['status'], 'inquiryId': inquiry_id}
