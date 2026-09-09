import json
import logging

from packages.agents.state import AgentState

logger = logging.getLogger("cortexbi.agents.nodes.target_framing")

TARGET_PROMPT = """You are a data science advisor. Given the column profiles below, decide whether predictive modeling is appropriate and, if so, which column is the best target.

## Dataset
- Rows: {row_count}
- Columns: {col_count}

## Column Profiles
{profiles_text}

## Correlations
{correlations_text}

## Instructions
Return a JSON object:
{{
  "task": "regression" | "classification" | "skip",
  "target": "<column_name or null>",
  "reason": "<one sentence explaining your choice>"
}}

Rules:
- Pick "regression" for a continuous numeric target (revenue, price, score, etc.)
- Pick "classification" for a binary or low-cardinality categorical target (churn, status, category with <=10 values)
- Pick "skip" if no column makes a sensible prediction target (all IDs, all dates, too few rows, no clear outcome variable)
- Never pick an ID column, date column, or index as the target
- Prefer columns that other columns could plausibly predict (outcome/measure variables, not input/dimension variables)
- If multiple candidates exist, pick the one with the strongest correlations to other columns

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
        if p.get("is_id_column"):
            parts.append("(ID column)")
        if p.get("is_datetime"):
            parts.append("(datetime)")
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


def _heuristic_target(profiles: list[dict], correlations: dict) -> dict:
    numeric_cols = [
        p for p in profiles
        if p["dtype"] in ("int64", "float64")
        and not p.get("is_id_column")
        and not p.get("is_datetime")
    ]
    if not numeric_cols:
        return {"task": "skip", "target": None, "reason": "No suitable numeric columns"}

    strong_pairs = correlations.get("strong_pairs", [])
    corr_counts: dict[str, float] = {}
    for pair in strong_pairs:
        for col in (pair["col1"], pair["col2"]):
            corr_counts[col] = corr_counts.get(col, 0) + abs(pair["correlation"])

    best = None
    best_score = -1.0
    for p in numeric_cols:
        score = corr_counts.get(p["column_name"], 0)
        if score > best_score:
            best_score = score
            best = p
    if best is None:
        best = numeric_cols[0]

    unique_ratio = (best.get("unique_count", 0) or 0) / max(1, best.get("total_count", 1))
    if best.get("unique_count", 0) <= 10 and unique_ratio < 0.05:
        task = "classification"
    else:
        task = "regression"

    return {"task": task, "target": best["column_name"], "reason": "Heuristic selection based on correlations"}


async def target_framing_node(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.store import ArtifactStore, JobStepManager

    run_id = state["run_id"]
    jsm = JobStepManager(db_session)

    if await jsm.is_completed(run_id, "target_framing"):
        logger.info("target_framing already completed, skipping")
        store = ArtifactStore(db_session)
        cached = await store.get(run_id, "target_framing")
        if cached:
            state["ml_task"] = cached.get("task", "skip")
            state["ml_target"] = cached.get("target")
        return state

    await jsm.start_step(run_id, "target_framing")
    try:
        profiles = state.get("column_profiles", [])
        correlations = state.get("correlations", {})
        eda_summary = state.get("eda_summary", {})
        row_count = eda_summary.get("row_count", 0)
        col_count = eda_summary.get("column_count", 0)

        if row_count < 20:
            result = {"task": "skip", "target": None, "reason": "Too few rows for modeling"}
        else:
            result = await _llm_target_framing(profiles, correlations, row_count, col_count)
            if result is None:
                result = _heuristic_target(profiles, correlations)

        if result["target"] and result["task"] != "skip":
            valid_cols = {p["column_name"] for p in profiles}
            if result["target"] not in valid_cols:
                logger.warning("LLM picked invalid target %s, falling back", result["target"])
                result = _heuristic_target(profiles, correlations)

        store = ArtifactStore(db_session)
        await store.put(run_id, "target_framing", "target_framing", result)

        state["ml_task"] = result["task"]
        state["ml_target"] = result.get("target")
        state["current_node"] = "target_framing"

        await jsm.end_step(run_id, "target_framing", "succeeded")
        logger.info("target_framing completed: task=%s, target=%s", result["task"], result.get("target"))
    except Exception as e:
        await jsm.end_step(run_id, "target_framing", "failed", str(e))
        state["ml_task"] = "skip"
        state["ml_target"] = None
        logger.exception("target_framing failed, setting task=skip: %s", e)

    return state


async def _llm_target_framing(
    profiles: list[dict], correlations: dict, row_count: int, col_count: int
) -> dict | None:
    from packages.agents.llm import get_llm, is_llm_available

    if not is_llm_available():
        return None

    try:
        llm = get_llm(temperature=0.1)
        prompt = TARGET_PROMPT.format(
            row_count=row_count,
            col_count=col_count,
            profiles_text=_profiles_to_text(profiles),
            correlations_text=_correlations_to_text(correlations),
        )

        response = await llm.ainvoke(prompt)
        text = response.content.strip()
        if text.startswith("```"):
            parts = text.split("\n", 1)
            text = parts[1] if len(parts) > 1 else parts[0][3:]
            text = text.rsplit("```", 1)[0].strip()

        result = json.loads(text)
        if result.get("task") not in ("regression", "classification", "skip"):
            logger.warning("LLM returned invalid task: %s", result.get("task"))
            return None
        logger.info("LLM target framing: %s", result.get("reason", ""))
        return result
    except Exception as e:
        logger.warning("LLM target framing failed: %s", e)
        return None
