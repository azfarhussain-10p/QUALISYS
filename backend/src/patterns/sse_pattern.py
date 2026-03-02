"""
QUALISYS — SSE (Server-Sent Events) Pattern Spike
Epic 2 / C2 (Retro 2026-02-26): Approved pattern for real-time agent progress streaming.

CONTRACT — every SSE endpoint in Epic 2 MUST follow this pattern:

EVENT FORMAT (strict):
    data: {"type": "<event_type>", "run_id": "<uuid>", "payload": {...}}\n\n

EVENT TYPES:
    queued    — agent step has been enqueued
    running   — agent step is executing (includes progress_pct, progress_label)
    complete  — agent step finished (includes artifact_id)
    error     — unrecoverable failure (includes error_code, message)
    heartbeat — keepalive (empty payload, sent every 15 seconds)

USAGE in FastAPI endpoint:
    @router.get("/events/agents/{run_id}")
    async def stream_agent_events(run_id: UUID, ...) -> StreamingResponse:
        return build_sse_response(
            event_generator=my_event_generator(run_id, ...),
        )

CLIENT RECONNECTION:
    Clients MUST handle reconnection using the EventSource API's built-in retry.
    Server MUST NOT emit Last-Event-ID (not required for MVP run-scoped streams).

Tenant isolation:
    The endpoint dependency MUST validate that run_id belongs to the current tenant
    before calling build_sse_response(). The generator itself is tenant-unaware.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

from fastapi.responses import StreamingResponse

# Heartbeat interval in seconds — keeps proxies and load-balancers from closing idle connections
_HEARTBEAT_INTERVAL = 15.0

# Allowed event type literals (enforced at serialisation time)
_VALID_EVENT_TYPES = frozenset(
    {"queued", "running", "complete", "error", "heartbeat", "dashboard_refresh"}
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SSEEvent:
    """
    A single Server-Sent Event.  Serialises to the wire format:
        data: {json}\n\n
    """
    type:    str                       # one of _VALID_EVENT_TYPES
    run_id:  uuid.UUID
    payload: dict[str, Any] = field(default_factory=dict)

    def to_wire(self) -> str:
        """
        Serialise to SSE wire format.
        Contract: exactly one 'data:' line followed by a blank line.
        """
        if self.type not in _VALID_EVENT_TYPES:
            raise ValueError(f"Unknown SSE event type: {self.type!r}")
        body = json.dumps(
            {"type": self.type, "run_id": str(self.run_id), "payload": self.payload},
            separators=(",", ":"),
        )
        return f"data: {body}\n\n"


# ---------------------------------------------------------------------------
# Heartbeat wrapper
# ---------------------------------------------------------------------------

async def _heartbeat_aware_stream(
    source:    AsyncGenerator[SSEEvent, None],
    run_id:    uuid.UUID,
    interval:  float = _HEARTBEAT_INTERVAL,
) -> AsyncGenerator[str, None]:
    """
    Wraps an SSEEvent generator. Emits heartbeat events when the source is idle
    for longer than `interval` seconds. Terminates when source is exhausted.
    """
    heartbeat = SSEEvent(type="heartbeat", run_id=run_id)

    async def _source_iter() -> AsyncGenerator[Optional[SSEEvent], None]:
        async for event in source:
            yield event

    source_task: Optional[asyncio.Task] = None
    gen         = _source_iter()

    while True:
        try:
            # Await the next event with a timeout
            event = await asyncio.wait_for(gen.__anext__(), timeout=interval)
            yield event.to_wire()
        except asyncio.TimeoutError:
            # Source silent for `interval` seconds — send heartbeat
            yield heartbeat.to_wire()
        except StopAsyncIteration:
            # Source exhausted — stream is done
            break


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_sse_response(
    event_generator: AsyncGenerator[SSEEvent, None],
    run_id:          Optional[uuid.UUID] = None,
    heartbeat_interval: float = _HEARTBEAT_INTERVAL,
) -> StreamingResponse:
    """
    Wrap an async SSEEvent generator in a FastAPI StreamingResponse.

    Args:
        event_generator:    Async generator that yields SSEEvent instances.
        run_id:             UUID for heartbeat events (defaults to uuid4 if omitted).
        heartbeat_interval: Seconds of silence before a keepalive heartbeat is sent.

    Returns:
        StreamingResponse with media_type="text/event-stream" and correct headers.
    """
    _run_id = run_id or uuid.uuid4()

    async def _byte_stream() -> AsyncGenerator[bytes, None]:
        async for wire_str in _heartbeat_aware_stream(
            source=event_generator,
            run_id=_run_id,
            interval=heartbeat_interval,
        ):
            yield wire_str.encode("utf-8")

    return StreamingResponse(
        content=_byte_stream(),
        media_type="text/event-stream",
        headers={
            # Disable buffering in Nginx / proxy layers
            "X-Accel-Buffering":   "no",
            "Cache-Control":       "no-cache",
            "Connection":          "keep-alive",
            "Transfer-Encoding":   "chunked",
        },
    )
