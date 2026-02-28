"""
Contract tests for sse_pattern.py — Epic 2 / C2 (Retro 2026-02-26)

These tests verify INTERFACE CONTRACTS and BEHAVIOUR GUARANTEES of the SSE pattern.
No HTTP server is started. StreamingResponse is tested via its content iterator.

Contracts verified:
  - SSEEvent.to_wire(): format is exactly "data: {json}\\n\\n"
  - SSEEvent.to_wire(): JSON contains type, run_id, payload fields
  - SSEEvent.to_wire(): unknown event type raises ValueError (type safety)
  - build_sse_response(): returns StreamingResponse with correct media_type
  - build_sse_response(): response headers include no-cache directives
  - Heartbeat emitted when generator is silent beyond interval
  - All valid event types are accepted (queued, running, complete, error, heartbeat)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncGenerator

import pytest

from src.patterns.sse_pattern import (
    SSEEvent,
    _VALID_EVENT_TYPES,
    build_sse_response,
)

RUN_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# SSEEvent.to_wire() — format contract
# ---------------------------------------------------------------------------

def test_event_to_wire_produces_correct_format():
    # Proves: wire format is exactly "data: {json}\n\n" — clients depend on this
    event  = SSEEvent(type="running", run_id=RUN_ID, payload={"progress_pct": 42})
    wire   = event.to_wire()
    assert wire.startswith("data: "), "Wire format must start with 'data: '"
    assert wire.endswith("\n\n"),     "Wire format must end with double newline"


def test_event_to_wire_json_contains_required_fields():
    # Proves: serialised JSON has type, run_id, payload — all fields clients parse
    event  = SSEEvent(type="complete", run_id=RUN_ID, payload={"artifact_id": "abc"})
    wire   = event.to_wire()
    body   = json.loads(wire.removeprefix("data: ").strip())
    assert body["type"]    == "complete"
    assert body["run_id"]  == str(RUN_ID)
    assert body["payload"] == {"artifact_id": "abc"}


def test_event_to_wire_empty_payload_is_valid():
    # Proves: heartbeat events with empty payload are serialised without error
    event = SSEEvent(type="heartbeat", run_id=RUN_ID)
    wire  = event.to_wire()
    body  = json.loads(wire.removeprefix("data: ").strip())
    assert body["payload"] == {}


def test_event_to_wire_rejects_unknown_event_type():
    # Proves: unknown event types raise ValueError to prevent silent client-side bugs
    event = SSEEvent(type="mystery_event", run_id=RUN_ID)
    with pytest.raises(ValueError, match="mystery_event"):
        event.to_wire()


# ---------------------------------------------------------------------------
# All valid event types accepted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("event_type", sorted(_VALID_EVENT_TYPES))
def test_all_valid_event_types_serialise_without_error(event_type: str):
    # Proves: each defined event type produces valid wire output (no regression on type list)
    event = SSEEvent(type=event_type, run_id=RUN_ID)
    wire  = event.to_wire()
    assert f'"type": "{event_type}"' in wire or f'"type":"{event_type}"' in wire


# ---------------------------------------------------------------------------
# build_sse_response() — response shape
# ---------------------------------------------------------------------------

async def _empty_generator() -> AsyncGenerator[SSEEvent, None]:
    """An immediately-exhausted generator for testing StreamingResponse construction."""
    return
    yield  # type: ignore[misc]


def test_build_sse_response_returns_streaming_response():
    # Proves: return type is StreamingResponse so FastAPI knows to stream the body
    from fastapi.responses import StreamingResponse
    response = build_sse_response(event_generator=_empty_generator(), run_id=RUN_ID)
    assert isinstance(response, StreamingResponse)


def test_build_sse_response_has_correct_media_type():
    # Proves: media_type is text/event-stream — required for browser EventSource API
    response = build_sse_response(event_generator=_empty_generator(), run_id=RUN_ID)
    assert response.media_type == "text/event-stream"


def test_build_sse_response_has_no_cache_header():
    # Proves: Cache-Control: no-cache header is set to prevent proxy buffering
    response = build_sse_response(event_generator=_empty_generator(), run_id=RUN_ID)
    assert response.headers.get("Cache-Control") == "no-cache"


def test_build_sse_response_has_accel_buffering_disabled():
    # Proves: X-Accel-Buffering: no is set to disable Nginx proxy buffering
    response = build_sse_response(event_generator=_empty_generator(), run_id=RUN_ID)
    assert response.headers.get("X-Accel-Buffering") == "no"


# ---------------------------------------------------------------------------
# Heartbeat emission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_heartbeat_emitted_on_generator_silence():
    # Proves: when the source generator is silent for interval seconds, a heartbeat
    #         event is emitted to keep the connection alive through proxies/LBs
    from src.patterns.sse_pattern import _heartbeat_aware_stream

    async def _slow_generator() -> AsyncGenerator[SSEEvent, None]:
        # Emits one event then waits longer than the heartbeat interval
        yield SSEEvent(type="queued", run_id=RUN_ID)
        await asyncio.sleep(0.3)  # > interval=0.1 used in test
        yield SSEEvent(type="complete", run_id=RUN_ID)

    collected = []
    async for wire in _heartbeat_aware_stream(
        source=_slow_generator(),
        run_id=RUN_ID,
        interval=0.1,  # short interval for fast test
    ):
        body = json.loads(wire.removeprefix("data: ").strip())
        collected.append(body["type"])

    # Expect: queued, (heartbeat), complete
    assert collected[0] == "queued"
    assert "heartbeat" in collected
    assert collected[-1] == "complete"


@pytest.mark.asyncio
async def test_stream_ends_when_generator_exhausted():
    # Proves: the heartbeat wrapper terminates when source generator is fully consumed
    from src.patterns.sse_pattern import _heartbeat_aware_stream

    async def _single_event() -> AsyncGenerator[SSEEvent, None]:
        yield SSEEvent(type="complete", run_id=RUN_ID)

    collected = []
    async for wire in _heartbeat_aware_stream(
        source=_single_event(),
        run_id=RUN_ID,
        interval=10.0,  # long interval — should NOT emit heartbeat
    ):
        collected.append(wire)

    # Only one event; stream must terminate
    assert len(collected) == 1
    body = json.loads(collected[0].removeprefix("data: ").strip())
    assert body["type"] == "complete"
