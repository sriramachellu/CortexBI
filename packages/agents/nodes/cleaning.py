import io
import json
import logging

import pandas as pd

from packages.agents.state import AgentState
from packages.agents.tools.pandas_tools import (
    clean_duplicates,
    detect_missing_values,
    infer_datetime_columns,
)

logger = logging.getLogger("cortexbi.agents.nodes.cleaning")

CLEANING_PROMPT = """You are a data cleaning expert. Analyze this dataset profile and decide the optimal cleaning strategy.

## Dataset Overview
- Rows: {row_count}
- Columns: {col_count}

## Column Details
{column_details}

## Missing Values
{missing_info}

## Sample Data (first 5 rows)
{sample_data}

## Instructions
For each column with issues, decide the best cleaning action. Return a JSON object with:
{{
  "strategy": {{
    "<column_name>": {{
      "action": "drop_column" | "fill_median" | "fill_mean" | "fill_mode" | "fill_zero" | "fill_forward" | "keep_as_is",
      "reason": "<brief explanation>"
    }}
  }},
  "drop_rows_with_missing": ["<col_name>", ...],
  "notes": "<brief overall assessment of data quality>"
}}

Rules:
- Drop columns with >60% missing data
- For numeric columns with <20% missing, fill_median is usually best
- For categorical columns, fill_mode is usually best
- For time-series data, fill_forward can be appropriate
- If a column is an ID or unique identifier, keep_as_is (don't impute)
- Only include columns that need action, skip clean columns

Return ONLY valid JSON, no markdown fences."""


def _build_column_details(df: pd.DataFrame) -> str:
    lines = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        nunique = df[col].nunique()
        lines.append(f"- {col}: dtype={dtype}, unique={nunique}")
    return "\n".join(lines)


def _build_missing_info(missing: dict) -> str:
    if not missing:
        return "No missing values detected."
    lines = []
    for col, info in missing.items():
        lines.append(f"- {col}: {info['count']} missing ({info['pct']:.1f}%)")
    return "\n".join(lines)


async def _llm_cleaning_strategy(df: pd.DataFrame, missing_info: dict) -> dict | None:
    from packages.agents.llm import get_llm, is_llm_available

    if not is_llm_available():
        return None

    try:
        llm = get_llm(temperature=0.0)
        sample = df.head(5).to_string(index=False, max_cols=20)

        prompt = CLEANING_PROMPT.format(
            row_count=len(df),
            col_count=len(df.columns),
            column_details=_build_column_details(df),
            missing_info=_build_missing_info(missing_info),
            sample_data=sample,
        )

        response = await llm.ainvoke(prompt)
        text = response.content.strip()
        if text.startswith("```"):
            parts = text.split("\n", 1)
            text = parts[1] if len(parts) > 1 else parts[0][3:]
            text = text.rsplit("```", 1)[0].strip()

        strategy = json.loads(text)
        logger.info("LLM cleaning strategy: %s", strategy.get("notes", ""))
        return strategy
    except Exception as e:
        logger.warning("LLM cleaning failed, falling back to static: %s", e)
        return None


def _apply_static_cleaning(df: pd.DataFrame, missing_info: dict) -> pd.DataFrame:
    for col, info in missing_info.items():
        if info["pct"] > 50:
            df = df.drop(columns=[col])
        elif pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
        else:
            mode_val = df[col].mode().iloc[0] if not df[col].mode().empty else "unknown"
            df[col] = df[col].fillna(mode_val)
    return df


def _apply_llm_strategy(df: pd.DataFrame, strategy: dict) -> tuple[pd.DataFrame, list[str]]:
    actions_taken = []
    col_strategies = strategy.get("strategy", {})

    for col, plan in col_strategies.items():
        if col not in df.columns:
            continue
        action = plan.get("action", "keep_as_is")
        reason = plan.get("reason", "")

        if action == "drop_column":
            df = df.drop(columns=[col])
            actions_taken.append(f"Dropped column '{col}': {reason}")
        elif action == "fill_median" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
            actions_taken.append(f"Filled '{col}' with median: {reason}")
        elif action == "fill_mean" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].mean())
            actions_taken.append(f"Filled '{col}' with mean: {reason}")
        elif action == "fill_mode":
            mode_val = df[col].mode().iloc[0] if not df[col].mode().empty else "unknown"
            df[col] = df[col].fillna(mode_val)
            actions_taken.append(f"Filled '{col}' with mode: {reason}")
        elif action == "fill_zero":
            df[col] = df[col].fillna(0)
            actions_taken.append(f"Filled '{col}' with 0: {reason}")
        elif action == "fill_forward":
            df[col] = df[col].ffill()
            actions_taken.append(f"Forward-filled '{col}': {reason}")

    drop_rows_cols = strategy.get("drop_rows_with_missing", [])
    for col in drop_rows_cols:
        if col in df.columns:
            before = len(df)
            df = df.dropna(subset=[col])
            actions_taken.append(f"Dropped {before - len(df)} rows with missing '{col}'")

    return df, actions_taken


async def cleaning_node(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.store import ArtifactStore, JobStepManager

    run_id = state["run_id"]
    jsm = JobStepManager(db_session)

    if await jsm.is_completed(run_id, "cleaning"):
        logger.info("cleaning already completed, skipping")
        store = ArtifactStore(db_session)
        cached = await store.get(run_id, "cleaning_report")
        if cached:
            state["cleaning_report"] = cached
            state["cleaned_storage_uri"] = cached.get("cleaned_storage_uri", "")
        return state

    await jsm.start_step(run_id, "cleaning")
    try:
        raw = storage.get(state["raw_storage_uri"])
        encoding = state.get("detected_encoding", "utf-8")
        df = pd.read_csv(io.BytesIO(raw), encoding=encoding)

        df, dedup_info = clean_duplicates(df)
        missing_info = detect_missing_values(df)

        llm_strategy = await _llm_cleaning_strategy(df, missing_info)
        actions_taken = []

        if llm_strategy:
            df, actions_taken = _apply_llm_strategy(df, llm_strategy)
            ai_driven = True
        else:
            df = _apply_static_cleaning(df, missing_info)
            ai_driven = False

        df, datetime_cols = infer_datetime_columns(df)

        cleaned_key = f"datasets/{state['dataset_id']}/cleaned.csv"
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        storage.put(cleaned_key, buf.getvalue())

        report = {
            "cleaned_storage_uri": cleaned_key,
            "duplicates": dedup_info,
            "missing_values_handled": {col: info for col, info in missing_info.items()},
            "datetime_columns_inferred": datetime_cols,
            "rows_after_cleaning": len(df),
            "columns_after_cleaning": len(df.columns),
            "ai_driven": ai_driven,
            "ai_actions": actions_taken,
            "ai_notes": llm_strategy.get("notes", "") if llm_strategy else "",
        }

        store = ArtifactStore(db_session)
        await store.put(run_id, "cleaning", "cleaning_report", report)

        state["cleaned_storage_uri"] = cleaned_key
        state["cleaning_report"] = report
        state["current_node"] = "cleaning"

        await jsm.end_step(run_id, "cleaning", "succeeded")
        logger.info(
            "cleaning completed (ai=%s): %d rows, %d cols, %d actions",
            ai_driven, len(df), len(df.columns), len(actions_taken),
        )
    except Exception as e:
        await jsm.end_step(run_id, "cleaning", "failed", str(e))
        state["error"] = str(e)
        state["status"] = "failed"
        raise

    return state
