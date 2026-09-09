import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Artifact, JobStep

logger = logging.getLogger("cortexbi.agents.store")


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


class ArtifactStore:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def put(self, run_id: str, agent: str, artifact_type: str, payload: dict) -> str:
        safe_payload = _sanitize(payload)
        result = await self._session.execute(
            select(Artifact.version)
            .where(Artifact.run_id == run_id, Artifact.type == artifact_type)
            .order_by(Artifact.version.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        next_ver = (row or 0) + 1

        artifact_id = str(uuid.uuid4())
        artifact = Artifact(
            artifact_id=artifact_id,
            run_id=run_id,
            agent=agent,
            type=artifact_type,
            payload_json=safe_payload,
            version=next_ver,
        )
        self._session.add(artifact)
        await self._session.flush()
        return artifact_id

    async def get(self, run_id: str, artifact_type: str) -> dict | None:
        result = await self._session.execute(
            select(Artifact.payload_json)
            .where(Artifact.run_id == run_id, Artifact.type == artifact_type)
            .order_by(Artifact.version.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row


class JobStepManager:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def start_step(self, run_id: str, node_name: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = pg_insert(JobStep).values(
            job_step_id=uuid.uuid4(),
            run_id=run_id,
            node_name=node_name,
            status="running",
            started_at=now,
            attempts=1,
        ).on_conflict_on_constraint("uq_job_steps_run_node").do_update(
            set_={
                "status": "running",
                "started_at": now,
                "attempts": JobStep.attempts + 1,
                "error": None,
                "ended_at": None,
            },
            where=JobStep.status.notin_(["running", "succeeded"]),
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def end_step(
        self, run_id: str, node_name: str, status: str, error: str | None = None,
    ) -> None:
        await self._session.execute(
            update(JobStep)
            .where(JobStep.run_id == run_id, JobStep.node_name == node_name)
            .values(status=status, error=error, ended_at=datetime.now(timezone.utc))
        )
        await self._session.flush()

    async def is_completed(self, run_id: str, node_name: str) -> bool:
        result = await self._session.execute(
            select(JobStep.status).where(
                JobStep.run_id == run_id, JobStep.node_name == node_name
            )
        )
        status = result.scalar_one_or_none()
        return status in ("succeeded", "skipped")
