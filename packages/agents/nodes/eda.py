import io
import json
import logging

import pandas as pd

from packages.agents.state import AgentState
from packages.agents.tools.pandas_tools import (
    compute_column_profiles,
    compute_correlations,
    detect_outliers_iqr,
)

logger = logging.getLogger("cortexbi.agents.nodes.eda")

ANALYSIS_PROMPT = """You are a senior data analyst. Analyze this dataset's statistical profile and provide insights.

## Dataset Shape
- Rows: {row_count}
- Columns: {col_count}

## Column Profiles
{profiles_text}

## Correlations
{correlations_text}

## Outliers
{outliers_text}

## Cleaning Report
{cleaning_notes}

## Instructions
Analyze the data and return a JSON object with:
{{
  "key_insights": [
    "<insight 1: a specific, actionable finding about the data>",
    "<insight 2>",
    "<insight 3>"
  ],
  "interesting_columns": ["<col1>", "<col2>"],
  "suggested_analyses": [
    "<what further analysis would be valuable>"
  ],
  "data_story": "<A 2-3 sentence narrative about what this dataset reveals>",
  "anomalies": ["<any surprising patterns or red flags>"],
  "recommended_kpis": [
    {{"column": "<col_name>", "aggregation": "mean|median|sum|count|min|max", "label": "<human-readable label>"}},
  ]
}}

Rules:
- Be specific — reference actual column names and values
- Focus on what's interesting or unusual, not obvious facts
- Key insights should be things a business user would find actionable
- Recommended KPIs should be the 3-5 most important summary statistics
- If correlations are strong, explain what they might mean
- If outliers exist, note whether they look like errors or genuine extremes

Return ONLY valid JSON, no markdown fences."""


def _profiles_to_text(profiles: list[dict]) -> str:
    lines = []
    for p in profiles:
        parts = [f"  {p['column_name']}: dtype={p['dtype']}"]
        if p.get("mean") is not None:
            parts.append(f"mean={p['mean']:.2f}, std={p.get('std', 0):.2f}")
            parts.append(f"min={p.get('min', 'N/A')}, max={p.get('max', 'N/A')}")
        parts.append(f"missing={p.get('missing_pct', 0):.1f}%")
        parts.append(f"unique={p.get('unique_count', 'N/A')}")
        lines.append(", ".join(parts))
    return "\n".join(lines)


def _correlations_to_text(correlations: dict) -> str:
    pairs = correlations.get("strong_pairs", [])
    if not pairs:
        return "No strong correlations found."
    lines = []
    for p in pairs[:10]:
        lines.append(f"  {p['col1']} <-> {p['col2']}: r={p['correlation']:.3f}")
    return "\n".join(lines)


def _outliers_to_text(outliers: dict) -> str:
    if not outliers:
        return "No outliers detected."
    lines = []
    for col, info in outliers.items():
        lines.append(f"  {col}: {info.get('count', 0)} outliers")
    return "\n".join(lines)


async def _llm_analyze(
    profiles: list[dict],
    correlations: dict,
    outliers: dict,
    cleaning_notes: str,
    row_count: int,
    col_count: int,
) -> dict | None:
    from packages.agents.llm import get_llm, is_llm_available

    if not is_llm_available():
        return None

    try:
        llm = get_llm(temperature=0.2)

        prompt = ANALYSIS_PROMPT.format(
            row_count=row_count,
            col_count=col_count,
            profiles_text=_profiles_to_text(profiles),
            correlations_text=_correlations_to_text(correlations),
            outliers_text=_outliers_to_text(outliers),
            cleaning_notes=cleaning_notes or "No cleaning was needed.",
        )

        response = await llm.ainvoke(prompt)
        text = response.content.strip()
        if text.startswith("```"):
            parts = text.split("\n", 1)
            text = parts[1] if len(parts) > 1 else parts[0][3:]
            text = text.rsplit("```", 1)[0].strip()

        analysis = json.loads(text)
        logger.info("LLM analysis complete: %d insights", len(analysis.get("key_insights", [])))
        return analysis
    except Exception as e:
        logger.warning("LLM analysis failed, continuing without insights: %s", e)
        return None


async def eda_node(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.store import ArtifactStore, JobStepManager

    run_id = state["run_id"]
    jsm = JobStepManager(db_session)

    if await jsm.is_completed(run_id, "eda"):
        logger.info("eda already completed, skipping")
        store = ArtifactStore(db_session)
        cached = await store.get(run_id, "eda_results")
        if cached:
            state["column_profiles"] = cached.get("column_profiles", [])
            state["correlations"] = cached.get("correlations", {})
            state["outliers"] = cached.get("outliers", {})
            state["eda_summary"] = cached
        return state

    await jsm.start_step(run_id, "eda")
    try:
        cleaned_uri = state.get("cleaned_storage_uri", state["raw_storage_uri"])
        raw = storage.get(cleaned_uri)
        encoding = state.get("detected_encoding", "utf-8")
        df = pd.read_csv(io.BytesIO(raw), encoding=encoding)

        profiles = compute_column_profiles(df)
        correlations = compute_correlations(df)
        outliers = detect_outliers_iqr(df)

        cleaning_report = state.get("cleaning_report", {})
        cleaning_notes = cleaning_report.get("ai_notes", "")

        llm_analysis = await _llm_analyze(
            profiles, correlations, outliers, cleaning_notes,
            row_count=len(df), col_count=len(df.columns),
        )

        eda_results = {
            "column_profiles": profiles,
            "correlations": correlations,
            "outliers": outliers,
            "row_count": len(df),
            "column_count": len(df.columns),
            "ai_analysis": llm_analysis,
        }

        store = ArtifactStore(db_session)
        await store.put(run_id, "eda", "eda_results", eda_results)

        state["column_profiles"] = profiles
        state["correlations"] = correlations
        state["outliers"] = outliers
        state["eda_summary"] = eda_results
        state["current_node"] = "eda"

        await jsm.end_step(run_id, "eda", "succeeded")
        logger.info(
            "eda completed (ai=%s): %d profiles",
            llm_analysis is not None, len(profiles),
        )
    except Exception as e:
        await jsm.end_step(run_id, "eda", "failed", str(e))
        state["error"] = str(e)
        state["status"] = "failed"
        raise

    return state
