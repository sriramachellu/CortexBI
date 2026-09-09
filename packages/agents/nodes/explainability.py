import io
import json
import logging

import joblib
import numpy as np
import pandas as pd
import shap

from packages.agents.nodes.modeling import _prepare_features
from packages.agents.state import AgentState

logger = logging.getLogger("cortexbi.agents.nodes.explainability")


async def explainability_node(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.store import ArtifactStore, JobStepManager

    run_id = state["run_id"]
    jsm = JobStepManager(db_session)

    if await jsm.is_completed(run_id, "explainability"):
        logger.info("explainability already completed, skipping")
        store = ArtifactStore(db_session)
        cached = await store.get(run_id, "shap_summary")
        if cached:
            state["shap_summary"] = cached
        return state

    ml_task = state.get("ml_task", "skip")
    model_uri = state.get("model_uri")

    if ml_task == "skip" or not model_uri:
        logger.info("explainability skipped: no model available")
        await jsm.start_step(run_id, "explainability")
        await jsm.end_step(run_id, "explainability", "skipped")
        return state

    await jsm.start_step(run_id, "explainability")
    try:
        from apps.api.config import settings
        shap_sample_size = settings.SHAP_SAMPLE_SIZE

        model_bytes = storage.get(model_uri)
        model = joblib.load(io.BytesIO(model_bytes))

        cleaned_uri = state.get("cleaned_storage_uri", state["raw_storage_uri"])
        raw = storage.get(cleaned_uri)
        encoding = state.get("detected_encoding", "utf-8")
        df = pd.read_csv(io.BytesIO(raw), encoding=encoding)

        ml_target = state.get("ml_target", "")
        if ml_task == "classification":
            df = df.dropna(subset=[ml_target])
            df[ml_target] = df[ml_target].astype(str)

        X, _ = _prepare_features(df, ml_target)

        model_features = state.get("model_metrics", {}).get("feature_names", [])
        if model_features:
            available = [f for f in model_features if f in X.columns]
            X = X[available]

        sample_size = min(len(X), shap_sample_size)
        if sample_size < len(X):
            X_sample = X.sample(n=sample_size, random_state=42)
        else:
            X_sample = X

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)

        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        feature_importance = sorted(
            zip(X_sample.columns.tolist(), mean_abs_shap.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )

        shap_summary = {
            "target": ml_target,
            "task": ml_task,
            "sample_size": sample_size,
            "feature_importance": [
                {"feature": name, "importance": round(imp, 6)}
                for name, imp in feature_importance
                if imp > 0.001
            ],
        }

        shap_data = {
            "shap_values": shap_values.tolist(),
            "feature_names": X_sample.columns.tolist(),
            "base_value": float(explainer.expected_value)
            if not isinstance(explainer.expected_value, np.ndarray)
            else float(explainer.expected_value[0]),
        }
        shap_key = f"datasets/{state['dataset_id']}/runs/{run_id}/shap_values.json"
        storage.put(shap_key, json.dumps(shap_data).encode())

        store = ArtifactStore(db_session)
        await store.put(run_id, "explainability", "shap_summary", shap_summary)

        state["shap_uri"] = shap_key
        state["shap_summary"] = shap_summary
        state["current_node"] = "explainability"

        await jsm.end_step(run_id, "explainability", "succeeded")
        logger.info(
            "explainability completed: %d features, sample_size=%d",
            len(shap_summary["feature_importance"]),
            sample_size,
        )
    except Exception as e:
        await jsm.end_step(run_id, "explainability", "failed", str(e))
        logger.exception("explainability failed: %s", e)

    return state
