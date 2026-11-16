"""Bounded gateway to the private, real SQL Server / Oracle learning lab."""
import os
import re
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from starlette.concurrency import run_in_threadpool

from app.portal.auth import same_origin
from app.portal.store import get_store, reserve_budget

router = APIRouter(prefix='/integration/api')
GET_PATH = re.compile(r'(status|cases|records/[a-f0-9]{64})\Z')
POST_PATH = re.compile(r'(import/(live|fixture)|cases|cases/[a-f0-9]{32}/review)\Z')


def availability():
    closes_at = os.getenv('INTEGRATION_CLOSES_AT', '')
    if closes_at:
        try:
            deadline = datetime.fromisoformat(closes_at.replace('Z', '+00:00'))
            if deadline.tzinfo is None:
                raise ValueError('Timezone required')
        except ValueError:
            return {'available': False, 'closes_at': None, 'code': 'service_unavailable',
                    'message': 'The demo service is temporarily unavailable.'}
        if datetime.now(timezone.utc) >= deadline:
            return {'available': False, 'closes_at': closes_at, 'code': 'demo_paused',
                    'message': 'This demo service is temporarily closed. The project and walkthrough remain available.'}
    return {'available': True, 'closes_at': closes_at or None}


@router.get('/availability')
async def integration_availability():
    from fastapi.responses import JSONResponse
    return JSONResponse(availability(), headers={'Cache-Control': 'no-store'})


def gateway_token():
    return id_token.fetch_id_token(GoogleRequest(), os.environ['INTEGRATION_TOKEN_AUDIENCE'])


@router.api_route('/{path:path}', methods=['GET', 'POST'])
async def integration_proxy(path: str, request: Request):
    if not (GET_PATH if request.method == 'GET' else POST_PATH).fullmatch(path):
        raise HTTPException(404, 'Unknown demo operation.')
    state = availability()
    if not state['available']:
        raise HTTPException(503, state)
    target = os.getenv('INTEGRATION_BACKEND_URL', '').rstrip('/')
    if not target:
        raise HTTPException(503, 'The cloud integration lab is starting. Please try again shortly.')
    body = b''
    if request.method == 'POST':
        same_origin(request)
        if request.headers.get('x-lab-request') != 'demo':
            raise HTTPException(403, 'Use the integration demo page.')
        async for chunk in request.stream():
            body += chunk
            if len(body) > 8192:
                raise HTTPException(413, 'Request is too large.')
        try:
            # This is a public synthetic-data lab. Bound shared cloud spending.
            limit = 40 if path == 'cases' else 200
            reserve_budget(get_store(), 'integration-' + ('model' if path == 'cases' else 'writes'), limit, 86400)
        except ValueError as exc:
            raise HTTPException(429, 'The shared demo has reached its daily limit. Please return tomorrow.') from exc
    try:
        token = await run_in_threadpool(gateway_token)
        async with httpx.AsyncClient(timeout=httpx.Timeout(20 if path == 'status' else 190, connect=3)) as client:
            upstream = await client.request(request.method, target + '/api/' + path, content=body,
                headers={'Authorization': 'Bearer ' + token, 'X-Lab-Request': 'demo', 'Content-Type': 'application/json'})
        if upstream.status_code in (401, 403) or upstream.status_code >= 500:
            raise HTTPException(502, 'The cloud lab could not complete this operation. Please try again shortly.')
        return Response(upstream.content, status_code=upstream.status_code, media_type='application/json',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except httpx.HTTPError as exc:
        raise HTTPException(502, 'The database lab is temporarily unavailable. Please retry.') from exc
