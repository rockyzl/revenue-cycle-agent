"""Small document-store interface: durable Firestore in cloud, SQLite locally.

Only server code has database access. Neither the browser nor the model receives
credentials or a general query interface. Authorization belongs in service.py.
"""
import json
import os
import sqlite3
import time
from functools import lru_cache
from pathlib import Path


class SQLiteStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS documents (collection TEXT, key TEXT, data TEXT, PRIMARY KEY(collection,key))')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def get(self, collection, key):
        with self.connect() as c:
            row = c.execute('SELECT data FROM documents WHERE collection=? AND key=?', (collection, key)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, collection, key, data):
        with self.connect() as c:
            c.execute('INSERT INTO documents VALUES(?,?,?) ON CONFLICT(collection,key) DO UPDATE SET data=excluded.data', (collection, key, json.dumps(data)))

    def create(self, collection, key, data):
        with self.connect() as c:
            c.execute('INSERT INTO documents VALUES(?,?,?)', (collection, key, json.dumps(data)))

    def delete(self, collection, key):
        with self.connect() as c:
            c.execute('DELETE FROM documents WHERE collection=? AND key=?', (collection, key))

    def query(self, collection, filters, limit=100):
        with self.connect() as c:
            rows = c.execute('SELECT data FROM documents WHERE collection=?', (collection,)).fetchall()
        docs = [json.loads(row[0]) for row in rows]
        return [d for d in docs if all(d.get(k) == v for k, v in filters.items())][:limit]

    def change(self, collection, key, operation):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT data FROM documents WHERE collection=? AND key=?', (collection, key)).fetchone()
            result = operation(json.loads(row[0]) if row else None)
            c.execute('INSERT INTO documents VALUES(?,?,?) ON CONFLICT(collection,key) DO UPDATE SET data=excluded.data', (collection, key, json.dumps(result)))
            return result


class FirestoreStore:
    def __init__(self):
        from google.cloud import firestore
        self.client = firestore.Client(project=os.environ['GOOGLE_CLOUD_PROJECT'], database=os.getenv('PORTAL_DATABASE', 'revenue-cycle-demo'))

    def get(self, collection, key):
        return self.client.collection(collection).document(key).get().to_dict()

    def put(self, collection, key, data):
        self.client.collection(collection).document(key).set(data)

    def create(self, collection, key, data):
        self.client.collection(collection).document(key).create(data)

    def delete(self, collection, key):
        self.client.collection(collection).document(key).delete()

    def query(self, collection, filters, limit=100):
        from google.cloud.firestore_v1.base_query import FieldFilter
        q = self.client.collection(collection)
        for key, value in filters.items():
            q = q.where(filter=FieldFilter(key, '==', value))
        return [d.to_dict() for d in q.limit(limit).stream()]

    def change(self, collection, key, operation):
        from google.cloud import firestore
        ref = self.client.collection(collection).document(key)
        @firestore.transactional
        def update(transaction):
            result = operation(ref.get(transaction=transaction).to_dict())
            transaction.set(ref, result)
            return result
        return update(self.client.transaction())


@lru_cache(maxsize=1)
def get_store():
    if os.getenv('PORTAL_STORE') == 'firestore':
        return FirestoreStore()
    return SQLiteStore(os.getenv('PORTAL_SQLITE_PATH', 'artifacts/portal.sqlite'))


def reserve_budget(store, key, limit, seconds):
    now = time.time()
    def increment(row):
        row = row or {'start': now, 'count': 0}
        if now - row['start'] >= seconds:
            row = {'start': now, 'count': 0}
        if row['count'] >= limit:
            raise ValueError('Demo request limit reached. Please try later.')
        return {**row, 'count': row['count'] + 1}
    store.change('limits', key, increment)
