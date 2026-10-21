"""Per-call, thread-local diagnostics so silent engine failures can be surfaced.

`TavilyClient.search()` calls `begin()`, engines call `note()` when something
goes wrong (HTTP errors, bot challenges, unparseable pages), and the client
attaches whatever was collected as `warnings` on the response.
"""

from __future__ import annotations

import logging
import threading
from typing import List

logger = logging.getLogger(__name__)

_tls = threading.local()
_MAX_NOTES = 10


def begin() -> None:
    """Start collecting diagnostics for the current thread/call."""
    _tls.msgs = []


def note(msg: str) -> None:
    """Record a diagnostic message (no-op outside a begin()/collect() window)."""
    logger.debug(msg)
    msgs = getattr(_tls, "msgs", None)
    if msgs is not None and msg not in msgs and len(msgs) < _MAX_NOTES:
        msgs.append(msg)


def collect() -> List[str]:
    """Return a copy of the messages recorded since begin()."""
    return list(getattr(_tls, "msgs", []))
