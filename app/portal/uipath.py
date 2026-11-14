"""Server-only confidential OAuth client; never uses a visitor's UiPath token."""
import asyncio
import json
import os
import time

import httpx
from fastapi import HTTPException

_cache = {'token': '', 'expires': 0}
_lock = asyncio.Lock()
SCOPES = 'OR.Jobs.Read OR.Jobs.Write OR.Execution.Read OR.Tasks.Read OR.Tasks.Write OR.Folders.Read'


async def access_token():
    async with _lock:
        if _cache['expires'] > time.time() + 60:
            return _cache['token']
        if not os.getenv('UIPATH_CLIENT_SECRET'):
            raise HTTPException(503, 'The UiPath connection is not configured.')
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.post('https://cloud.uipath.com/luagentlab/identity_/connect/token', data={'grant_type': 'client_credentials', 'client_id': os.environ['UIPATH_CLIENT_ID'], 'client_secret': os.environ['UIPATH_CLIENT_SECRET'], 'scope': SCOPES})
        if r.status_code != 200:
            raise HTTPException(502, 'UiPath authentication failed.')
        data = r.json()
        _cache.update(token=data['access_token'], expires=time.time() + data['expires_in'])
        return _cache['token']


async def request(method, path, **kwargs):
    token = await access_token()
    headers = {'Authorization': 'Bearer ' + token, 'X-UIPATH-FolderKey': os.environ['MAESTRO_FOLDER_KEY']}
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.request(method, 'https://cloud.uipath.com/luagentlab/DefaultTenant' + path, headers=headers, **kwargs)
    if r.status_code >= 400:
        raise HTTPException(502, f'UiPath request failed (HTTP {r.status_code}).')
    return r.json() if r.content else {}


async def start(inquiry_id, worker_token):
    release = os.getenv('MAESTRO_RELEASE_KEY')
    if not release:
        raise HTTPException(503, 'The Maestro workflow is not deployed.')
    result = await request('POST', '/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs', json={'startInfo': {'ReleaseKey': release, 'InputArguments': json.dumps({'inquiryId': inquiry_id, 'workerToken': worker_token}), 'JobsCount': 1, 'Strategy': 'ModernJobsCount'}})
    job = result['value'][0]
    return {'job_key': job['Key'], 'state': job['State']}


async def find_task(inquiry_id, job_key):
    # The plain /odata/Tasks endpoint enumerates classic folders only.
    # Match the immutable job key as well as our title in the modern-folder API.
    title = ('RC ' + inquiry_id).replace("'", "''")
    result = await request('GET', '/orchestrator_/odata/Tasks/UiPath.Server.Configuration.OData.GetTasksAcrossFolders', params={'$filter': f"Title eq '{title}'", '$top': 10})
    matches = [t for t in result.get('value', []) if t.get('CreatorJobKey') == job_key and t.get('Title') == 'RC ' + inquiry_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise HTTPException(409, 'Multiple review tasks were found. Staff investigation is required.')
    data = await request('GET', '/orchestrator_/tasks/GenericTasks/GetTaskDataById', params={'taskId': matches[0]['Id']})
    if data.get('title') != 'RC ' + inquiry_id or data.get('creatorJobKey') != job_key:
        raise HTTPException(409, 'The review task does not match this inquiry.')
    return data


async def complete_task(inquiry_id, job_key, decision, reply):
    task = await find_task(inquiry_id, job_key)
    if not task or str(task.get('status')) not in {'0', '1', 'Unassigned', 'Pending'}:
        raise HTTPException(409, 'The review task is not ready or has already completed. Please refresh.')
    await request('POST', '/orchestrator_/tasks/GenericTasks/CompleteTask', json={'type': 'QuickFormTask', 'taskId': task['id'], 'data': {'approvedReply': reply}, 'action': 'Approve' if decision == 'approve' else 'Reject'})
    return task['id']
