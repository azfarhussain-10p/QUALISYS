"""
QUALISYS — SSEManager
Story: 2-9-real-time-agent-progress-tracking

In-process asyncio.Queue registry for SSE event relay (AC-19, AC-19b).

Design:
  - SSEManager is a module-level singleton.
  - The SSE generator (events/router.py) calls get_or_create_queue() to create a queue
    for a given run_id and reads events from it.
  - The orchestrator calls publish() at every state transition (best-effort).
  - The generator calls remove_queue() in its finally block to clean up.

Concurrency: Single-process FastAPI (MVP). For multi-replica, replace with Redis pub/sub.
"""

from __future__ import annotations

import asyncio


class SSEManager:
    """In-process asyncio.Queue registry keyed by run_id."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}

    def get_or_create_queue(self, run_id: str) -> asyncio.Queue:
        """Return existing queue for run_id, or create a new one (maxsize=1000 safety bound)."""
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue(maxsize=1000)
        return self._queues[run_id]

    def remove_queue(self, run_id: str) -> None:
        """Remove queue from registry. No-op if not found."""
        self._queues.pop(run_id, None)

    async def publish(self, run_id: str, event_type: str, payload: dict) -> None:
        """
        Best-effort publish to the subscriber queue for run_id.
        Silent no-op if no queue is registered (orchestrator started before client connected).
        """
        q = self._queues.get(run_id)
        if q is not None:
            await q.put({"type": event_type, "payload": payload})


# Module-level singleton — import and use this directly
sse_manager = SSEManager()
