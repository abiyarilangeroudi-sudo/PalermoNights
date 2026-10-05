"""Bound public creation before allocating a game or making a model call."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import secrets
import time

from fastapi import HTTPException, Request, Response

ACTIVE = {'QUEUED', 'RUNNING', 'WAITING_FOR_HUMAN'}


def limit(name, default):
    return max(1, int(os.getenv(name, str(default))))


def local_access(request):
    if os.getenv('PALERMO_ALLOW_LOCAL_LIVE') != '1':
        return False
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except (ValueError, AttributeError):
        return False


def issue_session(request: Request, response: Response):
    key = os.getenv('PALERMO_PLAY_KEY', '')
    supplied = request.headers.get('x-play-key', '')
    if not key or not secrets.compare_digest(key, supplied):
        raise HTTPException(401, 'play access required')
    payload = f'{int(time.time()) + 3600}.{secrets.token_hex(16)}'
    signature = hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    response.set_cookie('palermo_access', f'{payload}.{signature}', httponly=True,
        secure=request.url.scheme == 'https', samesite='strict', max_age=3600, path='/')
    return {'success': True}


def authorize_live(request):
    if local_access(request):
        return
    key = os.getenv('PALERMO_PLAY_KEY', '')
    try:
        expiry, nonce, signature = request.cookies.get('palermo_access', '').split('.')
        expected = hmac.new(key.encode(), f'{expiry}.{nonce}'.encode(), hashlib.sha256).hexdigest()
        if key and int(expiry) > time.time() and secrets.compare_digest(signature, expected):
            return
    except (ValueError, TypeError):
        pass
    raise HTTPException(401, 'play access required')


class Admission:
    def __init__(self, runtime):
        self.runtime = runtime
        self.history = []

    def admit(self, request, *, live=False):
        with self.runtime.games.lock:
            return self._admit(request, live=live)

    def _admit(self, request, *, live=False):
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'cross-origin game creation is not allowed')
        if live:
            authorize_live(request)
        # Never trust client-provided X-Forwarded-For. Configure trusted proxies in uvicorn.
        client = request.client.host if request.client else 'unknown'
        if os.getenv('PALERMO_CLOUDFLARE_WORKER') == '1':
            client = request.headers.get('cf-connecting-ip', client)
        owner = hashlib.sha256(client.encode()).hexdigest()
        now = time.time()
        active = [r for r in self.runtime.runs._runs.values() if r.status in ACTIVE]
        if len(active) >= limit('PALERMO_MAX_ACTIVE_GAMES', 8):
            raise HTTPException(429, 'server game capacity reached', headers={'Retry-After': '60'})
        if sum(r.owner == owner for r in active) >= limit('PALERMO_MAX_ACTIVE_PER_CLIENT', 2):
            raise HTTPException(429, 'resume or end your existing game', headers={'Retry-After': '60'})
        store = self.runtime.store
        if store:
            rows = store.admissions_since(now - 86400)
        else:
            self.history = [r for r in self.history if r[2] > now - 86400]
            rows = self.history
        if sum(r[2] > now - 3600 for r in rows) >= limit('PALERMO_TOTAL_GAMES_PER_HOUR', 100):
            raise HTTPException(429, 'server creation limit reached', headers={'Retry-After': '3600'})
        if sum(r[0] == owner and r[2] > now - 3600 for r in rows) >= limit('PALERMO_GAMES_PER_HOUR', 10):
            raise HTTPException(429, 'hourly game limit reached', headers={'Retry-After': '3600'})
        if live and (sum(bool(r[1]) for r in rows) >= limit('PALERMO_LIVE_GAMES_PER_DAY', 20)
                     or sum(r.mode == 'live' for r in active) >= limit('PALERMO_MAX_ACTIVE_LIVE', 2)):
            raise HTTPException(429, 'live game budget reached', headers={'Retry-After': '3600'})
        record = (owner, int(live), now)
        if store:
            store.record_admission(record)
        else:
            self.history.append(record)
        return owner
