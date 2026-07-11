"""SLA urgency scoring.

Implements the dynamic urgency model from the specification:

    U(t) = S0 * exp(lambda_c * t)

where:
  * ``S0``       is the initial severity index computed on ingest (derived here
                 from the LLM criticality probability P(C=1|M)),
  * ``t``        is the time elapsed in minutes since the message arrived,
  * ``lambda_c`` is the channel-specific decay/priority constant (Discord >
                 Slack > Email), pulled from settings.

Tickets with a higher ``U(t)`` are forced to the top of the mobile dashboard's
list via query ordering, so this score is the single ranking signal for agents.

This module is pure and deterministic (no I/O), which keeps it trivially
testable and safe to call on every list read to "age" urgency forward in time.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from app.core.config import settings


def initial_severity(criticality: float) -> float:
    """Compute the initial severity index ``S0`` from criticality P(C=1|M).

    ``criticality`` is a probability in [0, 1]; we scale it by
    ``settings.severity_scale`` so a fresh, certainly-critical ticket starts
    near the top of the scale and a low-criticality ticket starts near zero.
    """
    clamped = min(max(criticality, 0.0), 1.0)
    return clamped * settings.severity_scale


def elapsed_minutes(since: datetime, *, now: datetime | None = None) -> float:
    """Return minutes elapsed between ``since`` and ``now`` (never negative).

    Both naive and timezone-aware datetimes are accepted; naive values are
    assumed to be UTC to match the timestamps persisted by the ORM.
    """
    reference = now or datetime.now(timezone.utc)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    delta = (reference - since).total_seconds() / 60.0
    return max(delta, 0.0)


def compute_urgency(
    *,
    criticality: float,
    channel: str,
    created_at: datetime,
    now: datetime | None = None,
) -> float:
    """Evaluate ``U(t) = S0 * exp(lambda_c * t)`` for a ticket.

    Args:
        criticality: LLM-derived P(C=1|M) in [0, 1], used to seed S0.
        channel: Source medium ('discord' | 'slack' | 'email') selecting lambda_c.
        created_at: When the message arrived (drives elapsed time t).
        now: Optional reference time for deterministic testing / batch aging.

    Returns:
        The urgency score, rounded to 4 decimal places.
    """
    s0 = initial_severity(criticality)
    lambda_c = settings.lambda_for_channel(channel)
    t = elapsed_minutes(created_at, now=now)
    urgency = s0 * math.exp(lambda_c * t)
    return round(urgency, 4)
