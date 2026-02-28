"""
QUALISYS — Agent Pipeline Orchestrator
Story: 2-7-agent-pipeline-orchestration

AC-17b: execute_pipeline() — top-level async function dispatched as FastAPI BackgroundTask.
AC-17c: agent_runs lifecycle: queued → running → completed | failed.
AC-17d: agent_run_steps lifecycle: queued → running → completed | failed.
AC-17e: _assemble_context() — loads doc chunks, github summary, crawl data.
AC-17f: _run_agent_step() — calls agent.run() via call_llm() with 3x retry.
AC-17g: _create_artifact() — INSERTs artifacts + artifact_versions rows.
AC-17h: Token tracking — step tokens_used + run total_tokens / total_cost_usd.
AC-17i: Error handling — 3x retry (5s/10s/20s); BudgetExceededError non-retryable.

Security (C1): All SQL via text() with :params — schema name only in f-string (validated upstream).
Session (C2): execute_pipeline opens its own AsyncSessionLocal session (request session is closed).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections import namedtuple
from datetime import datetime, timezone
from typing import Any

import tiktoken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import AsyncSessionLocal
from src.logger import logger
from src.patterns.llm_pattern import BudgetExceededError, LLMResult, call_llm
from src.services.agents.ba_consultant import BAConsultantAgent
from src.services.sse_manager import sse_manager
from src.services.agents.qa_consultant import QAConsultantAgent
from src.services.agents.automation_consultant import AutomationConsultantAgent
import src.services.agents.ba_consultant as _ba
import src.services.agents.qa_consultant as _qa
import src.services.agents.automation_consultant as _auto


# ---------------------------------------------------------------------------
# Shared data type
# ---------------------------------------------------------------------------

AgentResult = namedtuple(
    "AgentResult",
    ["content", "tokens_used", "cost_usd", "artifact_type", "content_type", "title"],
)

# Map agent_type string → (agent class, artifact metadata module)
AGENT_MAP: dict[str, tuple[type, Any]] = {
    "ba_consultant":         (BAConsultantAgent,         _ba),
    "qa_consultant":         (QAConsultantAgent,         _qa),
    "automation_consultant": (AutomationConsultantAgent, _auto),
}

# Retry configuration (AC-17i)
_RETRY_DELAYS = (5, 10, 20)  # seconds
_MAX_RETRIES  = 3

# Document chunks limit for context assembly (AC-17e, C8)
_DOC_CHUNK_LIMIT = 500
_DOC_TOKEN_LIMIT = 40_000


# ---------------------------------------------------------------------------
# AgentOrchestrator
# ---------------------------------------------------------------------------

class AgentOrchestrator:
    """Helper class providing private methods for the pipeline execution."""

    async def _assemble_context(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
    ) -> dict[str, str]:
        """
        AC-17e: Load project data from three sources.
        Returns {"doc_text": str, "github_summary": str, "crawl_data": str}.
        Missing sources return empty string — never raises.
        """
        enc = tiktoken.get_encoding("cl100k_base")

        # -- Document chunks (LIMIT 500, concatenated, truncated at 40k tokens)
        doc_text = ""
        try:
            result = await db.execute(
                text(
                    f"SELECT dc.content "
                    f'FROM "{schema_name}".document_chunks dc '
                    f'JOIN "{schema_name}".documents d ON d.id = dc.document_id '
                    f"WHERE d.project_id = :pid AND d.parse_status = 'completed' "
                    f"ORDER BY dc.document_id, dc.chunk_index "
                    f"LIMIT {_DOC_CHUNK_LIMIT}"
                ),
                {"pid": project_id},
            )
            chunks = [row[0] for row in result.fetchall() if row[0]]
            if chunks:
                combined = "\n\n".join(chunks)
                tokens   = enc.encode(combined)
                if len(tokens) > _DOC_TOKEN_LIMIT:
                    combined = enc.decode(tokens[:_DOC_TOKEN_LIMIT])
                    logger.warning(
                        "orchestrator: doc_text truncated",
                        project_id=project_id,
                        original_tokens=len(tokens),
                        limit=_DOC_TOKEN_LIMIT,
                    )
                doc_text = combined
        except Exception as exc:  # noqa: BLE001
            logger.warning("orchestrator: failed to load doc chunks", error=str(exc))

        # -- GitHub analysis summary (most recent cloned connection)
        github_summary = ""
        try:
            result = await db.execute(
                text(
                    f"SELECT analysis_summary "
                    f'FROM "{schema_name}".github_connections '
                    f"WHERE project_id = :pid AND status = 'cloned' "
                    f"ORDER BY created_at DESC LIMIT 1"
                ),
                {"pid": project_id},
            )
            row = result.fetchone()
            if row and row[0]:
                raw = row[0]
                github_summary = (
                    json.dumps(raw) if isinstance(raw, dict) else str(raw)
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("orchestrator: failed to load github summary", error=str(exc))

        # -- Crawl data (most recent completed session)
        crawl_data = ""
        try:
            result = await db.execute(
                text(
                    f"SELECT crawl_data "
                    f'FROM "{schema_name}".crawl_sessions '
                    f"WHERE project_id = :pid AND status = 'completed' "
                    f"ORDER BY created_at DESC LIMIT 1"
                ),
                {"pid": project_id},
            )
            row = result.fetchone()
            if row and row[0]:
                raw = row[0]
                crawl_data = json.dumps(raw) if isinstance(raw, dict) else str(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("orchestrator: failed to load crawl data", error=str(exc))

        return {
            "doc_text":       doc_text,
            "github_summary": github_summary,
            "crawl_data":     crawl_data,
        }

    async def _run_agent_step(
        self,
        db:         AsyncSession,
        schema_name: str,
        step_id:    str,
        agent_type: str,
        context:    dict,
        tenant_id:  str,
        user_id:    str,
        project_id: str,
        run_id:     str,
    ) -> AgentResult:
        """
        AC-17d/f/g/i: Transition step to running, call agent with retry,
        store artifact, transition step to completed.
        Raises on 3 consecutive LLM failures or non-retryable BudgetExceededError.
        """
        # Transition step → running
        now = datetime.now(timezone.utc)
        await self._update_step(
            db, schema_name, step_id,
            status="running", started_at=now,
        )
        # AC-19b: publish running event (best-effort)
        await sse_manager.publish(run_id, "running", {
            "step_id":        step_id,
            "agent_type":     agent_type,
            "progress_pct":   0,
            "progress_label": f"Agent {agent_type} is analyzing your project...",
        })

        # Instantiate agent
        agent_cls, meta_module = AGENT_MAP[agent_type]
        agent = agent_cls()

        # AC-18: compute context_hash once for stable cache key derivation
        context_hash = hashlib.sha256(
            json.dumps(context, sort_keys=True).encode()
        ).hexdigest()

        # AC-17i: retry loop (3× with 5s/10s/20s backoff)
        last_error: Exception | None = None
        llm_result: LLMResult | None = None

        for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
            try:
                llm_result = await agent.run(context, tenant_id, context_hash=context_hash)
                last_error = None
                break
            except BudgetExceededError:
                # Non-retryable — mark step failed then propagate immediately (AC-17d/i)
                now = datetime.now(timezone.utc)
                await self._update_step(
                    db, schema_name, step_id,
                    status="failed",
                    error_message="Token budget exceeded",
                    completed_at=now,
                )
                # AC-19b: publish error event (best-effort)
                await sse_manager.publish(run_id, "error", {
                    "step_id":    step_id,
                    "agent_type": agent_type,
                    "error_code": "STEP_FAILED",
                    "message":    "Token budget exceeded",
                })
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "orchestrator: LLM attempt failed",
                    agent_type=agent_type,
                    attempt=attempt,
                    error=str(exc),
                )
                if delay is not None:
                    await asyncio.sleep(delay)

        if last_error is not None or llm_result is None:
            error_msg = str(last_error) if last_error else "LLM returned no result"
            now = datetime.now(timezone.utc)
            await self._update_step(
                db, schema_name, step_id,
                status="failed",
                error_message=error_msg,
                completed_at=now,
            )
            # AC-19b: publish error event (best-effort)
            await sse_manager.publish(run_id, "error", {
                "step_id":    step_id,
                "agent_type": agent_type,
                "error_code": "STEP_FAILED",
                "message":    error_msg,
            })
            raise RuntimeError(
                f"Agent {agent_type} failed after {_MAX_RETRIES} retries: {error_msg}"
            )

        # Build AgentResult
        result = AgentResult(
            content=llm_result.content,
            tokens_used=llm_result.tokens_used,
            cost_usd=llm_result.cost_usd,
            artifact_type=meta_module.ARTIFACT_TYPE,
            content_type=meta_module.CONTENT_TYPE,
            title=meta_module.TITLE,
        )

        # AC-17g: persist artifact (Task 2.2: now returns artifact_id str)
        artifact_id = await self._create_artifact(
            db, schema_name, project_id, run_id, agent_type, result, user_id,
        )

        # AC-25: QA Consultant produces a secondary BDD artifact
        step_tokens_total = result.tokens_used
        step_cost_total = result.cost_usd
        if agent_type == "qa_consultant":
            bdd_last_error: Exception | None = None
            bdd_result_llm: LLMResult | None = None
            for bdd_attempt, bdd_delay in enumerate((*_RETRY_DELAYS, None), start=1):
                try:
                    bdd_result_llm = await agent.run_bdd(
                        context, tenant_id, context_hash=context_hash,
                    )
                    bdd_last_error = None
                    break
                except BudgetExceededError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    bdd_last_error = exc
                    logger.warning(
                        "orchestrator: BDD LLM attempt failed",
                        agent_type=agent_type,
                        attempt=bdd_attempt,
                        error=str(exc),
                    )
                    if bdd_delay is not None:
                        await asyncio.sleep(bdd_delay)

            if bdd_last_error is not None or bdd_result_llm is None:
                bdd_err = str(bdd_last_error) if bdd_last_error else "BDD LLM returned no result"
                raise RuntimeError(
                    f"Agent {agent_type} BDD failed after {_MAX_RETRIES} retries: {bdd_err}"
                )

            bdd_result = AgentResult(
                content=bdd_result_llm.content,
                tokens_used=bdd_result_llm.tokens_used,
                cost_usd=bdd_result_llm.cost_usd,
                artifact_type=_qa.BDD_ARTIFACT_TYPE,
                content_type=_qa.BDD_CONTENT_TYPE,
                title=_qa.BDD_TITLE,
            )
            await self._create_artifact(
                db, schema_name, project_id, run_id, agent_type, bdd_result, user_id,
            )
            step_tokens_total += bdd_result_llm.tokens_used
            step_cost_total += bdd_result_llm.cost_usd

        # Transition step → completed (AC-17d/h)
        now = datetime.now(timezone.utc)
        await self._update_step(
            db, schema_name, step_id,
            status="completed",
            tokens_used=step_tokens_total,
            progress_pct=100,
            completed_at=now,
        )
        # AC-19b: publish complete event (best-effort)
        await sse_manager.publish(run_id, "complete", {
            "step_id":    step_id,
            "agent_type": agent_type,
            "tokens_used": step_tokens_total,
            "artifact_id": artifact_id,
        })

        # Return result with combined tokens from primary + BDD calls
        return AgentResult(
            content=result.content,
            tokens_used=step_tokens_total,
            cost_usd=step_cost_total,
            artifact_type=result.artifact_type,
            content_type=result.content_type,
            title=result.title,
        )

    async def _create_artifact(
        self,
        db:           AsyncSession,
        schema_name:  str,
        project_id:   str,
        run_id:       str,
        agent_type:   str,
        result:       AgentResult,
        user_id:      str,
    ) -> str:
        """AC-17g: INSERT artifacts row + artifact_versions row (version=1). Returns artifact_id."""
        artifact_id = str(uuid.uuid4())
        now         = datetime.now(timezone.utc)

        metadata = json.dumps({
            "tokens_used": result.tokens_used,
            "cost_usd": result.cost_usd,
        })

        await db.execute(
            text(
                f'INSERT INTO "{schema_name}".artifacts '
                f"(id, project_id, run_id, agent_type, artifact_type, title, "
                f"current_version, metadata, created_by, created_at, updated_at) "
                f"VALUES (:id, :pid, :run_id, :agent_type, :artifact_type, :title, "
                f"1, :metadata, :created_by, :now, :now)"
            ),
            {
                "id":            artifact_id,
                "pid":           project_id,
                "run_id":        run_id,
                "agent_type":    agent_type,
                "artifact_type": result.artifact_type,
                "title":         result.title,
                "metadata":      metadata,
                "created_by":    user_id,
                "now":           now,
            },
        )

        version_id = str(uuid.uuid4())
        await db.execute(
            text(
                f'INSERT INTO "{schema_name}".artifact_versions '
                f"(id, artifact_id, version, content, content_type, diff_from_prev, created_at) "
                f"VALUES (:id, :artifact_id, 1, :content, :content_type, NULL, :now)"
            ),
            {
                "id":           version_id,
                "artifact_id":  artifact_id,
                "content":      result.content,
                "content_type": result.content_type,
                "now":          now,
            },
        )

        return artifact_id  # Task 2.2: return artifact_id for SSE complete event

    async def _update_run(
        self,
        db:          AsyncSession,
        schema_name: str,
        run_id:      str,
        **fields: Any,
    ) -> None:
        """UPDATE agent_runs WHERE id=:id with the provided keyword fields."""
        if not fields:
            return
        set_clauses = ", ".join(f"{k} = :{k}" for k in fields)
        await db.execute(
            text(
                f'UPDATE "{schema_name}".agent_runs '
                f"SET {set_clauses} WHERE id = :run_id"
            ),
            {"run_id": run_id, **fields},
        )

    async def _update_step(
        self,
        db:          AsyncSession,
        schema_name: str,
        step_id:     str,
        **fields: Any,
    ) -> None:
        """UPDATE agent_run_steps WHERE id=:id with the provided keyword fields."""
        if not fields:
            return
        set_clauses = ", ".join(f"{k} = :{k}" for k in fields)
        await db.execute(
            text(
                f'UPDATE "{schema_name}".agent_run_steps '
                f"SET {set_clauses} WHERE id = :step_id"
            ),
            {"step_id": step_id, **fields},
        )


# Module-level singleton
orchestrator = AgentOrchestrator()


# ---------------------------------------------------------------------------
# execute_pipeline — top-level coroutine passed to BackgroundTasks (AC-17b)
# ---------------------------------------------------------------------------

async def execute_pipeline(
    run_id:      str,
    schema_name: str,
    project_id:  str,
    tenant_id:   str,
    user_id:     str,
) -> None:
    """
    AC-17b/c/d/e/f/g/h/i: Background pipeline execution.

    Opens its own DB session (C2 — request session has already closed).
    Drives the full sequential pipeline: context assembly → per-agent steps → run completion.
    On any unrecoverable error: marks run failed before re-raising.
    """
    async with AsyncSessionLocal() as db:
        try:
            # AC-17c: transition run → running
            now = datetime.now(timezone.utc)
            await orchestrator._update_run(
                db, schema_name, run_id,
                status="running", started_at=now,
            )
            await db.commit()

            # Load agents_selected from the run row
            result = await db.execute(
                text(
                    f"SELECT agents_selected "
                    f'FROM "{schema_name}".agent_runs '
                    f"WHERE id = :id"
                ),
                {"id": run_id},
            )
            row = result.fetchone()
            if not row:
                raise RuntimeError(f"Run {run_id} not found in agent_runs")

            raw_agents = row[0]
            agents_selected: list[str] = (
                raw_agents if isinstance(raw_agents, list)
                else json.loads(raw_agents)
            )

            # Load step IDs in declared order
            steps_result = await db.execute(
                text(
                    f"SELECT id, agent_type "
                    f'FROM "{schema_name}".agent_run_steps '
                    f"WHERE run_id = :run_id "
                    f"ORDER BY agent_type"  # insertion order is preserved via agents_selected
                ),
                {"run_id": run_id},
            )
            # Build step_id lookup keyed by agent_type
            step_map: dict[str, str] = {row[1]: row[0] for row in steps_result.fetchall()}

            # AC-17e: assemble context once for all agents
            context = await orchestrator._assemble_context(db, schema_name, project_id)

            # AC-17c/d/h: sequential execution
            total_tokens   = 0
            total_cost_usd = 0.0

            for agent_type in agents_selected:
                step_id = step_map.get(agent_type)
                if not step_id:
                    logger.warning(
                        "orchestrator: step not found for agent",
                        agent_type=agent_type, run_id=run_id,
                    )
                    continue

                agent_result = await orchestrator._run_agent_step(
                    db=db,
                    schema_name=schema_name,
                    step_id=step_id,
                    agent_type=agent_type,
                    context=context,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    project_id=project_id,
                    run_id=run_id,
                )
                await db.commit()

                total_tokens   += agent_result.tokens_used
                total_cost_usd += agent_result.cost_usd

            # AC-17c: all steps succeeded — transition run → completed
            now = datetime.now(timezone.utc)
            await orchestrator._update_run(
                db, schema_name, run_id,
                status="completed",
                total_tokens=total_tokens,
                total_cost_usd=round(total_cost_usd, 6),
                completed_at=now,
            )
            await db.commit()

            # AC-19b: signal stream end to client (best-effort)
            await sse_manager.publish(run_id, "complete", {
                "run_id":   run_id,
                "all_done": True,
            })

            logger.info(
                "orchestrator: pipeline completed",
                run_id=run_id,
                total_tokens=total_tokens,
                agents=agents_selected,
            )

        except BudgetExceededError as exc:
            # AC-17i: non-retryable — mark run failed immediately
            now = datetime.now(timezone.utc)
            await orchestrator._update_run(
                db, schema_name, run_id,
                status="failed",
                error_message="Token budget exceeded",
                completed_at=now,
            )
            await db.commit()
            # AC-19b: best-effort SSE termination — notify client stream to close on failure
            try:
                await sse_manager.publish(run_id, "complete", {
                    "run_id":   run_id,
                    "all_done": True,
                    "error":    True,
                })
            except Exception:  # noqa: BLE001
                pass
            logger.error(
                "orchestrator: budget exceeded",
                run_id=run_id,
                tenant_id=exc.tenant_id,
                used=exc.used,
                limit=exc.limit,
            )

        except Exception as exc:  # noqa: BLE001
            # AC-17c: unrecoverable — mark run failed
            now = datetime.now(timezone.utc)
            try:
                await orchestrator._update_run(
                    db, schema_name, run_id,
                    status="failed",
                    error_message=str(exc),
                    completed_at=now,
                )
                await db.commit()
            except Exception as inner:  # noqa: BLE001
                logger.error(
                    "orchestrator: failed to mark run as failed",
                    run_id=run_id,
                    inner_error=str(inner),
                )
            # AC-19b: best-effort SSE termination — notify client stream to close on failure
            try:
                await sse_manager.publish(run_id, "complete", {
                    "run_id":   run_id,
                    "all_done": True,
                    "error":    True,
                })
            except Exception:  # noqa: BLE001
                pass
            logger.error("orchestrator: pipeline failed", run_id=run_id, error=str(exc))
