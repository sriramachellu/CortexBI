import io
import logging
import uuid

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier, XGBRegressor

from packages.agents.state import AgentState

logger = logging.getLogger("cortexbi.agents.nodes.modeling")

MIN_ROWS = 20
TEST_SIZE = 0.2


def _prepare_features(df: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.Series]:
    y = df[target].copy()
    X = df.drop(columns=[target])

    drop_cols = []
    for col in X.columns:
        if X[col].dtype == "object":
            nunique = X[col].nunique()
            if nunique > 50 or nunique == len(X):
                drop_cols.append(col)
        elif pd.api.types.is_datetime64_any_dtype(X[col]):
            drop_cols.append(col)
    X = X.drop(columns=drop_cols)

    cat_cols = X.select_dtypes(include=["object", "category"]).columns.tolist()
    if cat_cols:
        X = pd.get_dummies(X, columns=cat_cols, drop_first=True, dtype=float)

    X = X.apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median(numeric_only=True))
    remaining_nan = X.columns[X.isna().any()].tolist()
    if remaining_nan:
        X = X.drop(columns=remaining_nan)

    return X, y


def _train_model(
    X: pd.DataFrame, y: pd.Series, task: str
) -> tuple[object, dict, list[str]]:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=42
    )

    if task == "classification":
        model = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            eval_metric="logloss",
            verbosity=0,
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        metrics = {
            "task": "classification",
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "n_features": X.shape[1],
            "n_classes": int(y.nunique()),
        }
    else:
        model = XGBRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            verbosity=0,
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        r2 = float(r2_score(y_test, y_pred))
        metrics = {
            "task": "regression",
            "r2_score": r2,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "n_features": X.shape[1],
        }

    importances = model.feature_importances_
    feature_names = list(X.columns)
    top_features = sorted(
        zip(feature_names, importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )
    top_features = [(name, imp) for name, imp in top_features if imp > 0.01][:10]

    return model, metrics, feature_names


async def modeling_node(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.store import ArtifactStore, JobStepManager

    run_id = state["run_id"]
    jsm = JobStepManager(db_session)

    if await jsm.is_completed(run_id, "modeling"):
        logger.info("modeling already completed, skipping")
        store = ArtifactStore(db_session)
        cached = await store.get(run_id, "model_metrics")
        if cached:
            state["model_metrics"] = cached
        return state

    ml_task = state.get("ml_task", "skip")
    ml_target = state.get("ml_target")

    if ml_task == "skip" or not ml_target:
        logger.info("modeling skipped: task=%s", ml_task)
        await jsm.start_step(run_id, "modeling")
        await jsm.end_step(run_id, "modeling", "skipped")
        return state

    await jsm.start_step(run_id, "modeling")
    try:
        cleaned_uri = state.get("cleaned_storage_uri", state["raw_storage_uri"])
        raw = storage.get(cleaned_uri)
        encoding = state.get("detected_encoding", "utf-8")
        df = pd.read_csv(io.BytesIO(raw), encoding=encoding)

        if len(df) < MIN_ROWS:
            logger.info("modeling skipped: only %d rows", len(df))
            await jsm.end_step(run_id, "modeling", "skipped")
            return state

        if ml_target not in df.columns:
            logger.warning("target column %s not found, skipping modeling", ml_target)
            await jsm.end_step(run_id, "modeling", "skipped")
            state["ml_task"] = "skip"
            return state

        if ml_task == "classification":
            df = df.dropna(subset=[ml_target])
            df[ml_target] = df[ml_target].astype(str)

        X, y = _prepare_features(df, ml_target)

        if X.shape[1] == 0:
            logger.warning("no usable features after prep, skipping modeling")
            await jsm.end_step(run_id, "modeling", "skipped")
            state["ml_task"] = "skip"
            return state

        model, metrics, feature_names = _train_model(X, y, ml_task)
        metrics["target"] = ml_target
        metrics["feature_names"] = feature_names

        buf = io.BytesIO()
        joblib.dump(model, buf)
        buf.seek(0)
        model_key = f"datasets/{state['dataset_id']}/runs/{run_id}/model.joblib"
        storage.put(model_key, buf.read())

        store = ArtifactStore(db_session)
        await store.put(run_id, "modeling", "model_metrics", metrics)

        state["model_uri"] = model_key
        state["model_metrics"] = metrics
        state["current_node"] = "modeling"

        await jsm.end_step(run_id, "modeling", "succeeded")
        score_key = "accuracy" if ml_task == "classification" else "r2_score"
        logger.info(
            "modeling completed: task=%s, target=%s, %s=%.4f, features=%d",
            ml_task, ml_target, score_key, metrics[score_key], X.shape[1],
        )
    except Exception as e:
        await jsm.end_step(run_id, "modeling", "failed", str(e))
        state["ml_task"] = "skip"
        logger.exception("modeling failed: %s", e)

    return state
