"""Managed Identity Platform login; opaque server sessions shared by both portals.

Hospital federation/enrollment is not implemented. Seeded identities are public
fictional demo accounts. No role, patient id or grant is accepted from the browser.
"""
import os
import logging
import secrets
import time
from functools import lru_cache

import cachecontrol
import httpx
import requests
from fastapi import HTTPException, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from .service import Principal, account_for, digest, resolve_identity
from .store import get_store, reserve_budget

COOKIE = 'rc_portal_session'
SESSION_SECONDS = 1800
logging.getLogger('httpx').setLevel(logging.WARNING)


@lru_cache(maxsize=1)
def certificate_request():
    return GoogleRequest(session=cachecontrol.CacheControl(requests.Session()))


async def authenticate(email, password):
    api_key = os.getenv('IDENTITY_API_KEY')
    project = os.getenv('GOOGLE_CLOUD_PROJECT')
    if not api_key or not project:
        raise HTTPException(503, 'Sign-in is not configured yet.')
    # Avoid verbose HTTP-client logging: the upstream URL contains an API key.
    async with httpx.AsyncClient(timeout=20) as client:
        result = await client.post('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword', params={'key': api_key}, json={'email': email, 'password': password, 'returnSecureToken': True})
    if result.status_code != 200:
        raise HTTPException(401, 'Sign-in failed. Check the demo email and password.')
    token = result.json().get('idToken', '')
    try:
        claims = id_token.verify_firebase_token(token, certificate_request(), audience=project)
        if claims.get('iss') != f'https://securetoken.google.com/{project}':
            raise ValueError('Unexpected issuer')
        return claims
    except Exception as exc:
        raise HTTPException(401, 'Unable to verify the sign-in credentials.') from exc


def same_origin(request):
    origin = request.headers.get('origin')
    expected = os.getenv('PORTAL_ORIGIN') or str(request.base_url).rstrip('/')
    if origin and origin != expected:
        raise HTTPException(403, 'This request came from an untrusted origin.')


def create_session(store, claims):
    principal = resolve_identity(store, claims)
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expiry = min(time.time() + SESSION_SECONDS, float(claims['exp']))
    store.create('sessions', digest(token), {'account_id': principal.account_id, 'issuer': principal.issuer, 'subject': principal.subject, 'csrf': csrf, 'expires_at': expiry})
    return token, csrf, principal


def require_session(request: Request):
    store = get_store()
    token = request.cookies.get(COOKIE, '')
    row = store.get('sessions', digest(token)) if token else None
    if not row or row.get('expires_at', 0) <= time.time():
        raise HTTPException(401, 'Please sign in. Your session may have expired.')
    principal = Principal(row['account_id'], row['issuer'], row['subject'])
    account_for(store, principal)
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        same_origin(request)
        if not secrets.compare_digest(request.headers.get('x-csrf-token', ''), row['csrf']):
            raise HTTPException(403, 'Request verification failed. Please refresh the page.')
    return principal, row


def login_limit(request):
    key = 'login-' + digest(request.client.host if request.client else 'unknown')
    try:
        reserve_budget(get_store(), key, 15, 600)
    except ValueError as exc:
        raise HTTPException(429, str(exc)) from exc
