"""ORM models package.

Re-export models so importing ``app.models`` registers every table on
``Base.metadata`` (used by ``init_db``).
"""

from app.models.account import Account, ChannelConnection
from app.models.kb import KbChunk, KbDocument
from app.models.push import PushToken
from app.models.support import Ticket

__all__ = [
    "Account",
    "ChannelConnection",
    "Ticket",
    "PushToken",
    "KbDocument",
    "KbChunk",
]
