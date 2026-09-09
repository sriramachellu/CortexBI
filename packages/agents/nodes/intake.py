import io
import logging

import pandas as pd

from packages.agents.state import AgentState

logger = logging.getLogger("cortexbi.agents.nodes.intake")


async def intake_node(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.store import ArtifactStore, JobStepManager

    run_id = state["run_id"]
    jsm = JobStepManager(db_session)

    if await jsm.is_completed(run_id, "intake"):
        logger.info("intake already completed, skipping")
        store = ArtifactStore(db_session)
        cached = await store.get(run_id, "intake_schema")
        if cached:
            state["column_profiles"] = cached.get("columns_preview", [])
        return state

    await jsm.start_step(run_id, "intake")
    try:
        raw = storage.get(state["raw_storage_uri"])
        encoding = state.get("detected_encoding", "utf-8")
        df = pd.read_csv(io.BytesIO(raw), encoding=encoding)

        schema = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns_preview": [
                {"name": col, "dtype": str(df[col].dtype)} for col in df.columns
            ],
            "dtypes": {col: str(df[col].dtype) for col in df.columns},
        }

        store = ArtifactStore(db_session)
        await store.put(run_id, "intake", "intake_schema", schema)

        state["column_profiles"] = schema["columns_preview"]
        state["current_node"] = "intake"
        state["status"] = "running"

        await jsm.end_step(run_id, "intake", "succeeded")
        logger.info(
            "intake completed: %d rows, %d cols", schema["row_count"], schema["column_count"]
        )
    except Exception as e:
        await jsm.end_step(run_id, "intake", "failed", str(e))
        state["error"] = str(e)
        state["status"] = "failed"
        raise

    return state
