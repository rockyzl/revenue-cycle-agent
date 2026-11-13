"""Authorization boundary shared by HTTP routes and model tools."""
import hashlib
import time
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException

from .fixtures import grant_key, identity_key


@dataclass(frozen=True)
class Principal:
    account_id: str
    issuer: str
    subject: str


def audit(store, principal, action, resource, allowed):
    key = uuid4().hex
    store.create('audit', key, {'id': key, 'account_id': principal.account_id, 'action': action, 'resource': resource, 'allowed': allowed, 'at': time.time()})


def resolve_identity(store, claims):
    issuer, subject = claims.get('iss'), claims.get('sub')
    if not issuer or not subject:
        raise HTTPException(401, '登录身份无效，请重新登录。')
    link = store.get('identity_links', identity_key(issuer, subject))
    if not link or link.get('issuer') != issuer or link.get('subject') != subject:
        raise HTTPException(403, '这个登录身份尚未关联患者或工作人员账户。')
    p = Principal(link['account_id'], issuer, subject)
    account_for(store, p)
    return p


def account_for(store, principal):
    link = store.get('identity_links', identity_key(principal.issuer, principal.subject))
    account = store.get('accounts', principal.account_id)
    if not link or link.get('account_id') != principal.account_id or not account or not account.get('active'):
        raise HTTPException(403, '账户或身份关联已停用。')
    return account


def require_role(store, principal, role):
    account = account_for(store, principal)
    if account.get('role') != role:
        raise HTTPException(403, '当前账户没有执行此操作的权限。')
    return account


def has_patient_access(store, principal, patient_id):
    account = account_for(store, principal)
    if account.get('role') != 'patient':
        return False
    grant = store.get('access_grants', grant_key(principal.account_id, patient_id))
    return bool(grant and grant.get('active') and grant.get('account_id') == principal.account_id and grant.get('patient_id') == patient_id and grant.get('expires_at', 0) > time.time())


def authorized_bill(store, principal, bill_id):
    """Re-check the current grant on every read, including calls from the LLM."""
    bill = store.get('bills', bill_id)
    allowed = bool(bill and has_patient_access(store, principal, bill['patient_id']))
    audit(store, principal, 'read_bill', bill_id, allowed)
    if not allowed:
        # Same response for missing and unauthorized records; no existence oracle.
        raise HTTPException(404, '未找到可访问的账单。')
    return bill


def list_bills(store, principal):
    require_role(store, principal, 'patient')
    result = []
    for grant in store.query('access_grants', {'account_id': principal.account_id}):
        if has_patient_access(store, principal, grant['patient_id']):
            for bill in store.query('bills', {'patient_id': grant['patient_id']}):
                result.append(bill | {'relationship': grant['relationship']})
    return sorted(result, key=lambda b: b['id'])


def visible_inquiry(store, principal, inquiry_id):
    account = account_for(store, principal)
    row = store.get('inquiries', inquiry_id)
    allowed = bool(row and ((account['role'] == 'patient' and row['account_id'] == principal.account_id and has_patient_access(store, principal, row['patient_id'])) or (account['role'] == 'reviewer' and row.get('reviewer_id') == principal.account_id)))
    if not allowed:
        audit(store, principal, 'read_inquiry', inquiry_id, False)
        raise HTTPException(404, '未找到可访问的咨询。')
    return row


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()
