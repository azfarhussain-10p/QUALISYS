"""
QUALISYS — Artifact Service
Story: 2-10-test-artifact-storage-viewer (read ops)
       2-11-artifact-editing-versioning (update_artifact write op)
AC-26: CRUD operations for AI-generated test artifacts + version management.
AC-28: Save edited content as new artifact version (update_artifact).

Security (C1, C2):
  - All queries use SQLAlchemy text() with named :params
  - Schema name only in f-string (double-quoted), never from user input
"""

import difflib
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ArtifactService:
    """Artifact queries and write operations. Orchestrator handles initial artifact creation."""

    async def list_artifacts(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
        artifact_type: Optional[str] = None,
    ) -> list[dict]:
        sql = (
            f'SELECT id, agent_type, artifact_type, title, current_version, metadata, '
            f'created_by, created_at, updated_at '
            f'FROM "{schema_name}".artifacts '
            f'WHERE project_id = :pid '
            + ('AND artifact_type = :at ' if artifact_type else '')
            + 'ORDER BY created_at DESC'
        )
        params: dict = {"pid": project_id}
        if artifact_type:
            params["at"] = artifact_type

        result = await db.execute(text(sql), params)
        rows = result.mappings().fetchall()
        return [
            {
                "id": str(row["id"]),
                "agent_type": row["agent_type"],
                "artifact_type": row["artifact_type"],
                "title": row["title"],
                "current_version": row["current_version"],
                "metadata": row["metadata"],
                "created_by": str(row["created_by"]) if row["created_by"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]

    async def get_artifact(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
        artifact_id: str,
    ) -> dict:
        result = await db.execute(
            text(
                f'SELECT a.id, a.agent_type, a.artifact_type, a.title, '
                f'a.current_version, a.metadata, a.created_by, a.created_at, a.updated_at, '
                f'av.content, av.content_type '
                f'FROM "{schema_name}".artifacts a '
                f'JOIN "{schema_name}".artifact_versions av '
                f'  ON av.artifact_id = a.id AND av.version = a.current_version '
                f'WHERE a.id = :aid AND a.project_id = :pid'
            ),
            {"aid": artifact_id, "pid": project_id},
        )
        row = result.mappings().fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ARTIFACT_NOT_FOUND", "message": "Artifact not found."},
            )
        return {
            "id": str(row["id"]),
            "agent_type": row["agent_type"],
            "artifact_type": row["artifact_type"],
            "title": row["title"],
            "current_version": row["current_version"],
            "metadata": row["metadata"],
            "created_by": str(row["created_by"]) if row["created_by"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "content": row["content"],
            "content_type": row["content_type"],
        }

    async def list_versions(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
        artifact_id: str,
    ) -> list[dict]:
        owner_check = await db.execute(
            text(
                f'SELECT id FROM "{schema_name}".artifacts '
                f'WHERE id = :aid AND project_id = :pid'
            ),
            {"aid": artifact_id, "pid": project_id},
        )
        if owner_check.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ARTIFACT_NOT_FOUND", "message": "Artifact not found."},
            )

        result = await db.execute(
            text(
                f'SELECT id, version, content_type, edited_by, created_at '
                f'FROM "{schema_name}".artifact_versions '
                f'WHERE artifact_id = :aid '
                f'ORDER BY version DESC'
            ),
            {"aid": artifact_id},
        )
        rows = result.mappings().fetchall()
        return [
            {
                "id": str(row["id"]),
                "version": row["version"],
                "content_type": row["content_type"],
                "edited_by": str(row["edited_by"]) if row["edited_by"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

    async def get_version(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
        artifact_id: str,
        version: int,
    ) -> dict:
        result = await db.execute(
            text(
                f'SELECT a.id, a.agent_type, a.artifact_type, a.title, '
                f'a.current_version, a.metadata, a.created_by, a.created_at, a.updated_at, '
                f'av.content, av.content_type '
                f'FROM "{schema_name}".artifacts a '
                f'JOIN "{schema_name}".artifact_versions av '
                f'  ON av.artifact_id = a.id AND av.version = :ver '
                f'WHERE a.id = :aid AND a.project_id = :pid'
            ),
            {"aid": artifact_id, "pid": project_id, "ver": version},
        )
        row = result.mappings().fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "VERSION_NOT_FOUND", "message": "Artifact version not found."},
            )
        return {
            "id": str(row["id"]),
            "agent_type": row["agent_type"],
            "artifact_type": row["artifact_type"],
            "title": row["title"],
            "current_version": row["current_version"],
            "metadata": row["metadata"],
            "created_by": str(row["created_by"]) if row["created_by"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "content": row["content"],
            "content_type": row["content_type"],
        }

    async def update_artifact(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
        artifact_id: str,
        content: str,
        edited_by: str,
    ) -> dict:
        """Save edited content as new artifact version (AC-28).

        Raises HTTPException(404, ARTIFACT_NOT_FOUND) if artifact/project mismatch.
        """
        current = await self.get_artifact(db, schema_name, project_id, artifact_id)

        diff_lines = list(
            difflib.unified_diff(
                current["content"].splitlines(),
                content.splitlines(),
                lineterm="",
            )
        )
        diff_from_prev = "\n".join(diff_lines)
        new_version = current["current_version"] + 1

        await db.execute(
            text(
                f'INSERT INTO "{schema_name}".artifact_versions '
                f"(artifact_id, version, content, content_type, diff_from_prev, edited_by) "
                f"VALUES (:aid, :ver, :content, :ct, :diff, :eby)"
            ),
            {
                "aid": artifact_id,
                "ver": new_version,
                "content": content,
                "ct": current["content_type"],
                "diff": diff_from_prev,
                "eby": edited_by,
            },
        )
        await db.execute(
            text(
                f'UPDATE "{schema_name}".artifacts '
                f"SET current_version = :ver, updated_at = NOW() "
                f"WHERE id = :aid"
            ),
            {"ver": new_version, "aid": artifact_id},
        )
        await db.commit()

        return await self.get_artifact(db, schema_name, project_id, artifact_id)


artifact_service = ArtifactService()
