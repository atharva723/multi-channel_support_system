"""Triage endpoint.

``POST /support/triage`` is the tenant-scoped ingestion point for every
normalized platform message. The handler orchestrates the full pipeline:

    0. Resolve the owning account (Bearer session, or by inbound external_ref).
    1. Idempotency guard on (account, channel, message_id).
    2. Classify criticality P(C=1|M) via the LLM router.
    3. Draft a conversational reply.
    4. Score urgency U(t) at ingest.
    5. Persist the ticket (scoped to the account) and return the routing decision.

The decision tells the caller which branch to take: ESCALATED -> pushed over SSE
to that account's dashboard; AUTO_REPLY -> draft to be delivered to the source.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ApiKeyGuard, Broker, DBSession, Router
from app.core.config import settings
from app.models.support import Ticket
from app.schemas.triage import (
    EscalationTicket,
    SupportIngestPayload,
    TriageDecision,
    TriageResult,
)
from app.services import connections as conn_store
from app.services.auth import SessionTokenError, decode_session_token
from app.services.events import Event, EventBroker
from app.services.llm_router import LLMRouter, LLMRouterError
from app.services.providers import provider_for_channel
from app.services.urgency import compute_urgency

router = APIRouter(prefix="/support", tags=["triage"])


async def _resolve_account_id(
    payload: SupportIngestPayload,
    db: AsyncSession,
    authorization: str | None,
) -> int:
    """Determine which tenant a message belongs to.

    Prefers an authenticated Bearer session (e.g. an agent test-posting); falls
    back to resolving the account from the inbound ``external_ref`` mapped via the
    provider that owns the channel (how real provider webhooks attribute events).
    """
    if authorization and authorization.lower().startswith("bearer "):
        try:
            return decode_session_token(authorization.split(" ", 1)[1].strip())
        except SessionTokenError:
            pass

    if payload.external_ref:
        provider = provider_for_channel(payload.channel)
        account_id = await conn_store.resolve_account_by_external_ref(
            db, provider=provider, external_ref=payload.external_ref
        )
        if account_id is not None:
            return account_id

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            "Cannot resolve tenant: provide a Bearer session token or an "
            "external_ref that matches a connected channel."
        ),
    )


@router.post(
    "/triage",
    response_model=TriageResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ApiKeyGuard],
    summary="Ingest, classify, score, and route a support message",
)
async def triage_message(
    payload: SupportIngestPayload,
    db: AsyncSession = DBSession,
    llm: LLMRouter = Router,
    broker: EventBroker = Broker,
    authorization: str | None = Header(default=None),
) -> TriageResult:
    account_id = await _resolve_account_id(payload, db, authorization)

    # 1. Idempotency, scoped to this tenant + channel.
    existing = await db.scalar(
        select(Ticket).where(
            Ticket.account_id == account_id,
            Ticket.channel == payload.channel,
            Ticket.message_id == payload.message_id,
        )
    )
    if existing is not None:
        return _build_result(existing)

    # 2 & 3. Run the LLM router: criticality + draft reply.
    try:
        classification = await llm.classify_criticality(payload.content)
        draft_reply = await llm.generate_draft_reply(
            content=payload.content, author_name=payload.author_name
        )
    except LLMRouterError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM router failure: {exc}",
        ) from exc

    criticality = classification.criticality

    # 4. Urgency U(t) = S0 * exp(lambda_c * t) at ingest (t≈0, so U0 = S0).
    urgency = compute_urgency(
        criticality=criticality,
        channel=payload.channel,
        created_at=payload.timestamp,
    )

    # 5. Persist (scoped to the resolved account).
    ticket = Ticket(
        account_id=account_id,
        channel=payload.channel,
        channel_id=payload.channel_id,
        message_id=payload.message_id,
        author_name=payload.author_name,
        author_contact=payload.author_contact,
        content=payload.content,
        criticality_score=criticality,
        urgency_score=urgency,
        ai_draft_reply=draft_reply,
        status="PENDING",
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    result = _build_result(ticket)

    # 6. If escalated, push it to THIS account's connected dashboards over SSE.
    if result.is_critical:
        await broker.publish(
            Event(
                type="escalation",
                data=result.ticket.model_dump(mode="json"),
                account_id=account_id,
            )
        )

    return result


def _build_result(ticket: Ticket) -> TriageResult:
    """Assemble the API response (decision + metrics + persisted ticket)."""
    is_critical = ticket.criticality_score >= settings.criticality_threshold
    decision = (
        TriageDecision.ESCALATED if is_critical else TriageDecision.AUTO_REPLY
    )
    return TriageResult(
        decision=decision,
        is_critical=is_critical,
        criticality_score=ticket.criticality_score,
        urgency_score=ticket.urgency_score,
        threshold=settings.criticality_threshold,
        ticket=EscalationTicket.model_validate(ticket),
    )
