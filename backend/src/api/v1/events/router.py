"""
QUALISYS — Events SSE Endpoints
Story: 2-9-real-time-agent-progress-tracking (agent run SSE)
Story: 2-12-pm-csm-dashboard-project-health-overview (dashboard SSE)

AC-19: GET /api/v1/events/agent-runs/{run_id}
  - Returns StreamingResponse with Content-Type: text/event-stream
  - Uses build_sse_response() from src.patterns.sse_pattern (C2-approved pattern)
  - RBAC: require_project_role("owner", "admin", "qa-automation")
  - Validates run_id exists in tenant schema; raises 404 RUN_NOT_FOUND if absent
  - Heartbeat (15 s) handled automatically by build_sse_response — no manual heartbeat code here

AC-32: GET /api/v1/events/dashboard/{project_id}
  - Emits dashboard_refresh event every 30 seconds (asyncio.sleep loop, NOT SSEManager)
  - RBAC: require_project_role("owner", "admin", "qa-automation", "pm-csm")
  - Validates project exists in tenant schema; raises 404 PROJECT_NOT_FOUND if absent

Security (C2 / C5): resource validated in tenant schema BEFORE starting stream.
Generators themselves are tenant-unaware.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.patterns.sse_pattern import SSEEvent, build_sse_response
from src.services.sse_manager import sse_manager
from src.services.tenant_provisioning import slug_to_schema_name

router = APIRouter(tags=["Events"])


@router.get("/api/v1/events/agent-runs/{run_id}")
async def agent_run_sse_endpoint(
    run_id: uuid.UUID,
    auth:   tuple = require_project_role("owner", "admin", "qa-automation"),
    db:     AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    AC-19: Stream real-time SSE events for an agent pipeline run.

    Validates run_id belongs to the current tenant, then opens a streaming
    response backed by an in-process asyncio.Queue (SSEManager).
    """
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    result = await db.execute(
        text(f'SELECT id FROM "{schema_name}".agent_runs WHERE id = :run_id'),
        {"run_id": str(run_id)},
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "RUN_NOT_FOUND", "message": "Agent run not found."},
        )

    return build_sse_response(
        event_generator=_event_generator(str(run_id)),
        run_id=run_id,
    )


async def _event_generator(run_id: str) -> AsyncGenerator[SSEEvent, None]:
    """
    Async generator that reads from the SSEManager queue for run_id.

    Queue lifecycle:
      - Created here via get_or_create_queue() (lazy — after 201 response sent)
      - Cleaned up in finally block via remove_queue()

    Termination conditions:
      - Receives None sentinel (explicit stream close)
      - Receives complete event with payload.all_done == True
      - Client disconnects (FastAPI/Starlette closes the generator)
    """
    q = sse_manager.get_or_create_queue(run_id)
    try:
        while True:
            data = await q.get()
            if data is None:
                # Sentinel — explicit stream close requested
                return
            event_type = data.get("type", "error")
            yield SSEEvent(
                type=event_type,
                run_id=uuid.UUID(run_id),
                payload=data.get("payload", {}),
            )
            # Terminate after the run-level complete signal
            if event_type == "complete" and data.get("payload", {}).get("all_done"):
                return
    finally:
        sse_manager.remove_queue(run_id)


# ---------------------------------------------------------------------------
# Story 2.12 — Dashboard SSE endpoint (AC-32)
# ---------------------------------------------------------------------------

@router.get("/api/v1/events/dashboard/{project_id}")
async def dashboard_sse_endpoint(
    project_id: uuid.UUID,
    auth: tuple = require_project_role("owner", "admin", "qa-automation", "pm-csm"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    AC-32: Stream 30-second heartbeat SSE events for PM dashboard auto-refresh.

    Validates project_id belongs to the current tenant, then opens a streaming
    response that emits a dashboard_refresh event every 30 seconds.
    Client-side EventSource.close() on unmount triggers FastAPI to cancel generator.
    """
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    result = await db.execute(
        text(f'SELECT id FROM "{schema_name}".projects WHERE id = :pid'),
        {"pid": str(project_id)},
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PROJECT_NOT_FOUND", "message": "Project not found."},
        )

    return build_sse_response(
        event_generator=_dashboard_event_generator(str(project_id)),
        run_id=project_id,
    )


async def _dashboard_event_generator(project_id: str) -> AsyncGenerator[SSEEvent, None]:
    """
    AC-32: Async generator that emits a dashboard_refresh event every 30 seconds.

    Runs indefinitely — FastAPI cancels this generator when the client disconnects
    (EventSource.close() on component unmount).
    Does NOT use SSEManager (queue-based); uses simple asyncio.sleep loop instead.
    """
    while True:
        await asyncio.sleep(30)
        yield SSEEvent(
            type="dashboard_refresh",
            run_id=uuid.UUID(project_id),
            payload={"project_id": project_id},
        )
