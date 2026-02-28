"""
Unit tests for SSEManager (Story 2-9, Task 5.1)
Each test has a one-line comment stating the behaviour proved (A6 — Epic 1 retrospective action).
"""

import asyncio

import pytest

from src.services.sse_manager import SSEManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager() -> SSEManager:
    """Fresh SSEManager instance for each test (avoids singleton state bleed)."""
    return SSEManager()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_get_or_create_queue_creates_new_queue(manager: SSEManager) -> None:
    # Proves: first call for an unknown run_id creates a new asyncio.Queue
    q = manager.get_or_create_queue("run-1")
    assert isinstance(q, asyncio.Queue)


def test_get_or_create_queue_returns_same_queue(manager: SSEManager) -> None:
    # Proves: two calls for the same run_id return the identical queue instance
    q1 = manager.get_or_create_queue("run-1")
    q2 = manager.get_or_create_queue("run-1")
    assert q1 is q2


def test_get_or_create_queue_different_runs_are_independent(manager: SSEManager) -> None:
    # Proves: different run_ids get distinct queue instances
    q1 = manager.get_or_create_queue("run-A")
    q2 = manager.get_or_create_queue("run-B")
    assert q1 is not q2


@pytest.mark.asyncio
async def test_publish_puts_event_in_queue(manager: SSEManager) -> None:
    # Proves: publish() enqueues the event dict {type, payload} into the subscriber queue
    q = manager.get_or_create_queue("run-1")
    await manager.publish("run-1", "running", {"step_id": "s1", "progress_pct": 0})
    item = q.get_nowait()
    assert item == {"type": "running", "payload": {"step_id": "s1", "progress_pct": 0}}


@pytest.mark.asyncio
async def test_publish_no_op_when_no_subscriber(manager: SSEManager) -> None:
    # Proves: publish() with no registered queue raises no exception (silent no-op)
    await manager.publish("unknown-run", "running", {"step_id": "s1"})  # must not raise


def test_remove_queue_cleans_up(manager: SSEManager) -> None:
    # Proves: remove_queue() deletes the queue; run_id is no longer in the registry
    manager.get_or_create_queue("run-1")
    manager.remove_queue("run-1")
    assert "run-1" not in manager._queues


def test_remove_queue_no_op_when_not_found(manager: SSEManager) -> None:
    # Proves: remove_queue() on an unknown run_id raises no exception
    manager.remove_queue("does-not-exist")  # must not raise
