"""Ticket management endpoints.

Backs the mobile Escalation Desk. Three operations:

  * ``GET /support/tickets``      — list tickets for the dashboard, ranked by
    *aged* urgency U(t) (recomputed to "now" so older unattended tickets rise),
    optionally filtered by status.
  * ``GET /support/tickets/{id}`` — fetch a single ticket.
  * ``PATCH /support/tickets/{id}`` — an agent action (APPROVE / MODIFY /
    DISMISS). Updates status (and optionally the reply text) and publishes a
    ``ticket_update`` event so every connected dashboard reflects the change
    in real time.

Urgency is intentionally recomputed on read rather than stored-and-stale: the
spec's U(t) = S0 * e^(lambda_c * t) grows with wait time, so ranking must age.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Broker, CurrentAccount, DBSession
from app.models.account import Account
from app.models.support import Ticket
from app.schemas.triage import (
    EscalationTicket,
    TicketStatus,
    TicketStatusUpdate,
)
from app.services.events import Event, EventBroker
from app.services.sender import SendError, send_reply
from app.services.urgency import compute_urgency

router = APIRouter(prefix="/support", tags=["tickets"])


def _to_schema(ticket: Ticket) -> EscalationTicket:
    """Serialize a Ticket, refreshing urgency_score to the current time."""
    aged = compute_urgency(
        criticality=ticket.criticality_score,
        channel=ticket.channel,
        created_at=ticket.created_at,
    )
    schema = EscalationTicket.model_validate(ticket)
    return schema.model_copy(update={"urgency_score": aged})


@router.get(
    "/tickets",
    response_model=list[EscalationTicket],
    summary="List tickets ranked by current (aged) urgency",
)
async def list_tickets(
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
    status_filter: TicketStatus | None = Query(
        default=None,
        alias="status",
        description="Optional exact status filter (e.g. PENDING).",
    ),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EscalationTicket]:
    stmt = select(Ticket).where(Ticket.account_id == account.id)
    if status_filter is not None:
        stmt = stmt.where(Ticket.status == status_filter.value)
    # Pull a bounded set (roughly newest first) then rank by aged urgency in
    # Python, since U(t) depends on elapsed time and per-channel lambda.
    stmt = stmt.order_by(Ticket.created_at.desc()).limit(limit)
    rows = (await db.scalars(stmt)).all()

    tickets = [_to_schema(t) for t in rows]
    tickets.sort(key=lambda t: t.urgency_score, reverse=True)
    return tickets


@router.get(
    "/tickets/{ticket_id}",
    response_model=EscalationTicket,
    summary="Fetch a single ticket",
)
async def get_ticket(
    ticket_id: int,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> EscalationTicket:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None or ticket.account_id != account.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found."
        )
    return _to_schema(ticket)


@router.patch(
    "/tickets/{ticket_id}",
    response_model=EscalationTicket,
    summary="Agent action on a ticket (approve / modify / dismiss)",
)
async def update_ticket(
    ticket_id: int,
    payload: TicketStatusUpdate,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
    broker: EventBroker = Broker,
) -> EscalationTicket:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None or ticket.account_id != account.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found."
        )

    ticket.status = payload.status.value
    if payload.ai_draft_reply is not None:
        ticket.ai_draft_reply = payload.ai_draft_reply

    # Approving or modifying means "send this reply" through THIS account's
    # connected channel. Send BEFORE committing so we never mark a reply sent
    # that failed to leave.
    should_send = payload.status in (TicketStatus.APPROVED, TicketStatus.MODIFIED)
    if should_send:
        try:
            await send_reply(db, account_id=account.id, ticket=ticket)
        except SendError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Reply send failed: {exc}",
            ) from exc

    await db.commit()
    await db.refresh(ticket)

    result = _to_schema(ticket)
    # Notify this account's dashboards so the card updates in real time.
    await broker.publish(
        Event(
            type="ticket_update",
            data=result.model_dump(mode="json"),
            account_id=account.id,
        )
    )
    return result
