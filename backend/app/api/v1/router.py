"""Aggregate router for API v1.

Collects every v1 endpoint module under a single router that ``main.py`` mounts
at the configured API prefix. New feature routers (tickets, SSE stream) are
included here as later phases add them.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, kb, notifications, stream, tickets, triage

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(triage.router)
api_router.include_router(tickets.router)
api_router.include_router(stream.router)
api_router.include_router(notifications.router)
api_router.include_router(kb.router)
