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

import logging

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
from app.services import kb as kb_service
from app.services import push as push_service
from app.services.auth import SessionTokenError, decode_session_token
from app.services.events import Event, EventBroker
from app.services.llm_router import LLMRouter, LLMRouterError
from app.services.providers import provider_for_channel
from app.services.sender import SendError, send_reply
from app.services.urgency import compute_urgency

router = APIRouter(prefix="/support", tags=["triage"])

logger = logging.getLogger("sentinel.triage")


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
        # Discord community servers: auto-link the guild in dev if unmapped.
        if payload.channel == "discord" and settings.discord_auto_link_guild:
            account_id = await conn_store.autolink_discord_guild(
                db, payload.external_ref
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

    # 2 & 3. Run the LLM router: criticality + KB-grounded draft reply.
    try:
        classification = await llm.classify_criticality(payload.content)

        # RAG: ground the reply in the account's knowledge base when present.
        #  - relevant context found -> grounded reply
        #  - KB exists but nothing relevant -> out-of-scope, defer to a human
        #  - no KB at all -> general reply (unchanged behavior)
        context = await kb_service.retrieve(
            db, account_id=account_id, query=payload.content
        )
        out_of_scope = False
        if not context and await kb_service.account_has_kb(db, account_id=account_id):
            out_of_scope = True

        draft_reply = await llm.generate_draft_reply(
            content=payload.content,
            author_name=payload.author_name,
            context=context,
            out_of_scope=out_of_scope,
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

    if result.is_critical:
        # Escalated: push it to THIS account's connected dashboards over SSE.
        await broker.publish(
            Event(
                type="escalation",
                data=result.ticket.model_dump(mode="json"),
                account_id=account_id,
            )
        )
        # Also send a native push so the agent is alerted even if the app is
        # closed. Best-effort — never let a push failure break triage.
        try:
            preview = ticket.content.replace("\n", " ").strip()
            if len(preview) > 120:
                preview = preview[:117] + "…"
            await push_service.send_to_account(
                db,
                account_id=account_id,
                title=f"Critical: {ticket.author_name}",
                body=preview or "New high-priority ticket.",
                data={"url": f"/ticket/{ticket.id}", "ticketId": ticket.id},
            )
        except Exception as exc:  # noqa: BLE001 - best-effort side channel
            logger.warning("Push notify failed for ticket %s: %s", ticket.id, exc)
    elif settings.auto_reply_enabled:
        # Non-critical: let the AI reply on its own through the account's channel.
        # Best-effort — if the send fails, leave the ticket PENDING for manual
        # handling rather than failing the whole triage request.
        try:
            await send_reply(db, account_id=account_id, ticket=ticket)
            ticket.status = "AUTO_REPLIED"
            await db.commit()
            await db.refresh(ticket)
            result = _build_result(ticket)
            await broker.publish(
                Event(
                    type="ticket_update",
                    data=result.ticket.model_dump(mode="json"),
                    account_id=account_id,
                )
            )
        except SendError as exc:
            logger.warning(
                "Auto-reply send failed for ticket %s (%s); left PENDING: %s",
                ticket.id,
                ticket.channel,
                exc,
            )
            await db.rollback()

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
