import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agents.graph import run_pipeline
from packages.agents.state import AgentState
from packages.db.models import AnalysisRun, ColumnProfile, Dataset
from packages.storage.local import LocalDiskStore

logger = logging.getLogger("cortexbi.worker")


async def execute_pipeline(
    dataset_id: str,
    run_id: str,
    storage_uri: str,
    original_filename: str,
    detected_encoding: str,
    user_id: str,
    db_session: AsyncSession,
) -> None:
    storage = LocalDiskStore()

    await db_session.execute(
        update(AnalysisRun)
        .where(AnalysisRun.run_id == run_id)
        .values(status="running", started_at=datetime.now(timezone.utc))
    )
    await db_session.execute(
        update(Dataset)
        .where(Dataset.dataset_id == dataset_id)
        .values(status="analyzing")
    )
    await db_session.commit()

    state: AgentState = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "user_id": user_id,
        "raw_storage_uri": storage_uri,
        "original_filename": original_filename,
        "detected_encoding": detected_encoding,
        "current_node": "",
        "status": "running",
        "tool_call_log": [],
    }

    try:
        state = await run_pipeline(state, storage=storage, db_session=db_session)

        final_status = state.get("status", "completed")
        now = datetime.now(timezone.utc)

        model_metrics = state.get("model_metrics", {})
        run_updates = {
            "status": final_status,
            "completed_at": now,
            "dashboard_spec_uri": state.get("dashboard_spec_uri"),
            "cleaned_data_uri": state.get("cleaned_storage_uri"),
            "ml_task": state.get("ml_task"),
            "ml_target": state.get("ml_target"),
            "model_uri": state.get("model_uri"),
            "shap_uri": state.get("shap_uri"),
            "model_accuracy": model_metrics.get("accuracy"),
            "model_r2_score": model_metrics.get("r2_score"),
        }

        started = await db_session.execute(
            update(AnalysisRun)
            .where(AnalysisRun.run_id == run_id)
            .values(**run_updates)
            .returning(AnalysisRun.started_at)
        )
        started_at = started.scalar_one_or_none()
        if started_at:
            duration = (now - started_at).total_seconds()
            await db_session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.run_id == run_id)
                .values(processing_time_seconds=duration)
            )

        ds_status = "completed" if final_status == "completed" else "failed"
        await db_session.execute(
            update(Dataset)
            .where(Dataset.dataset_id == dataset_id)
            .values(status=ds_status)
        )

        profiles = state.get("column_profiles", [])
        if profiles:
            await db_session.execute(
                delete(ColumnProfile).where(ColumnProfile.run_id == run_id)
            )
            for p in profiles:
                cp = ColumnProfile(
                    run_id=run_id,
                    column_name=p["column_name"],
                    dtype=p["dtype"],
                    missing_count=p.get("missing_count"),
                    missing_pct=p.get("missing_pct"),
                    unique_count=p.get("unique_count"),
                    unique_pct=p.get("unique_pct"),
                    mean=p.get("mean"),
                    std=p.get("std"),
                    min=p.get("min"),
                    max=p.get("max"),
                    q25=p.get("q25"),
                    q50=p.get("q50"),
                    q75=p.get("q75"),
                    top_values=p.get("top_values"),
                    is_id_column=p.get("is_id_column", False),
                    is_datetime=p.get("is_datetime", False),
                    has_outliers=p.get("has_outliers", False),
                )
                db_session.add(cp)

        await db_session.commit()
        logger.info("pipeline completed for run %s", run_id)

    except Exception as e:
        logger.exception("pipeline failed for run %s", run_id)
        try:
            await db_session.rollback()
            await db_session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.run_id == run_id)
                .values(
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db_session.execute(
                update(Dataset)
                .where(Dataset.dataset_id == dataset_id)
                .values(status="failed")
            )
            await db_session.commit()
        except Exception as recovery_err:
            logger.exception("failed to persist error state: %s", recovery_err)
