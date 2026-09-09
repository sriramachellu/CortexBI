import io
import json
import logging
import math

import numpy as np
import pandas as pd

from packages.agents.state import AgentState

logger = logging.getLogger("cortexbi.agents.nodes.dashboard_builder")

# ---------------------------------------------------------------------------
# Domain detection
# ---------------------------------------------------------------------------

DOMAIN_KEYWORDS = {
    "sales": [
        "revenue", "price", "order", "units_sold", "product", "category",
        "customer", "quantity", "discount", "sku", "transaction", "purchase",
        "sale", "item", "cart", "shipping", "store", "retail",
    ],
    "marketing": [
        "campaign", "channel", "impression", "click", "conversion", "ctr",
        "spend", "lead", "bounce", "session", "visitor", "traffic", "ad",
        "engagement", "reach", "follower", "subscriber", "email", "open_rate",
    ],
    "people": [
        "employee", "salary", "department", "hire", "tenure", "performance",
        "attrition", "manager", "title", "role", "team", "headcount",
        "compensation", "benefit", "leave", "review", "gender", "age",
    ],
    "finance": [
        "cost", "budget", "expense", "profit", "margin", "vendor",
        "inventory", "invoice", "payment", "account", "balance",
        "debit", "credit", "tax", "liability", "asset",
    ],
}

DOMAIN_DESCRIPTIONS = {
    "sales": "Sales & E-commerce — products, transactions, revenue, customers",
    "marketing": "Marketing & Growth — campaigns, channels, conversions, engagement",
    "people": "People & HR — employees, compensation, performance, teams",
    "finance": "Finance & Operations — costs, budgets, margins, vendors",
    "general": "General dataset analysis",
}


def _detect_domain(profiles: list[dict]) -> str:
    col_names = {p["column_name"].lower().replace("_", " ") for p in profiles}
    col_words = set()
    for name in col_names:
        col_words.update(name.split())
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in col_words or kw in col_names)
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "general"


# ---------------------------------------------------------------------------
# Story-mode LLM prompt
# ---------------------------------------------------------------------------

STORY_PROMPT = """You are a world-class data storyteller presenting findings to a CEO who has 5 minutes.
Your job: tell the STORY in the data, not just show charts. Write for someone with zero technical background.

## Dataset
- Domain: {domain} ({domain_description})
- Rows: {row_count}, Columns: {col_count}

## Column Profiles
{profiles_text}

## Correlations
{correlations_text}

## Outliers
{outliers_text}

## AI Analysis
{insights_text}

## Cleaning Summary
{cleaning_summary}

## Available Chart Types
- "bar": Categories vs numeric. Config: x_column, y_column, aggregation (mean|sum|count|median), top_n, sort_by (value|name)
- "histogram": Distribution. Config: x_column, bins (default 15)
- "scatter": Relationship. Config: x_column, y_column
- "pie": Composition (max 6 slices). Config: x_column
- "line": Trend. Config: x_column, y_columns (list)
- "grouped_bar": Multi-series comparison. Config: x_column, y_columns (list), aggregation

## Instructions
Tell the STORY in this data. Think like a journalist writing a magazine feature, not a data analyst making a dashboard.

Return ONLY valid JSON (no markdown fences):
{{
  "hero": {{
    "headline": "<the #1 finding — specific, surprising, plain English>",
    "big_number": "<most important number, pre-formatted: '$10.4M', '73%', '2.96/5'>",
    "big_number_label": "<what it measures, 2-4 words>",
    "big_number_context": "<comparison or benchmark, e.g. 'vs industry avg of 4.1'>",
    "summary": "<2-3 sentence executive summary for someone who reads nothing else>"
  }},
  "insights": [
    {{
      "finding": "<one-sentence finding in plain English — no column names>",
      "detail": "<one supporting data point or explanation>",
      "sentiment": "positive|negative|neutral",
      "metric_value": "<key number, pre-formatted>",
      "metric_label": "<what it is, 2-3 words>"
    }}
  ],
  "story_sections": [
    {{
      "title": "<insight-driven headline — what the reader should take away>",
      "narrative": "<2-3 sentences: what does this part of the data show? why should the reader care?>",
      "chart": {{
        "type": "bar|histogram|scatter|pie|line|grouped_bar",
        "title": "<human-readable chart title>",
        "x_column": "<column>",
        "y_column": "<column (single-series)>",
        "y_columns": ["<col1>", "<col2>"],
        "aggregation": "mean|sum|count|median",
        "top_n": null,
        "sort_by": "value|name|null",
        "bins": 15
      }}
    }}
  ],
  "recommendations": [
    "<specific actionable recommendation — start with a verb, be specific enough to act on>"
  ],
  "kpis": [
    {{
      "label": "<human label — 'Average Order Value' not 'price'>",
      "column": "<column_name>",
      "aggregation": "mean|sum|count|median|min|max",
      "format": "number|currency|percent|integer",
      "comparison_text": "<optional context>"
    }}
  ]
}}

Rules:
- hero.headline: Specific and surprising. BAD: "Revenue is $10M". GOOD: "Your top 10 products generate 70% of all revenue".
- insights: Exactly 3-4 findings. Complete sentences a non-technical person understands. NO column names, NO technical terms.
- story_sections: Exactly 2-3 sections. Each tells ONE part of the story with ONE chart.
- recommendations: Exactly 2-3. Start with a verb. Specific enough to act on TODAY.
- kpis: 3-5 key metrics for the detail view.
- NEVER use raw column names in text. "Revenue" not "revenue". "Product Category" not "Beverage_category".
- Use {domain} terminology where appropriate."""


# ---------------------------------------------------------------------------
# Helpers (unchanged from v3)
# ---------------------------------------------------------------------------

def _safe_val(v):
    if v is None:
        return None
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        if math.isnan(v) or math.isinf(v):
            return None
        return float(v)
    return v


def _profiles_to_text(profiles: list[dict]) -> str:
    lines = []
    for p in profiles:
        parts = [f"  {p['column_name']}: dtype={p['dtype']}"]
        if p.get("mean") is not None:
            parts.append(f"mean={p['mean']:.2f}, std={p.get('std', 0):.2f}")
            parts.append(f"range=[{p.get('min', 'N/A')}, {p.get('max', 'N/A')}]")
        parts.append(f"missing={p.get('missing_pct', 0):.1f}%")
        parts.append(f"unique={p.get('unique_count', 'N/A')}")
        if p.get("has_outliers"):
            parts.append("HAS OUTLIERS")
        if p.get("is_datetime"):
            parts.append("DATETIME")
        lines.append(", ".join(parts))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chart data builders
# ---------------------------------------------------------------------------

def _build_bar_data(df, x_col, y_col, aggregation="mean", top_n=None, sort_by=None):
    agg_fn = aggregation if aggregation in ("mean", "sum", "count", "median", "min", "max") else "mean"
    if agg_fn == "count":
        grouped = df.groupby(x_col).size().reset_index(name=y_col)
    else:
        grouped = df.groupby(x_col)[y_col].agg(agg_fn).reset_index()
    if sort_by == "value":
        grouped = grouped.sort_values(y_col, ascending=False)
    elif sort_by == "name":
        grouped = grouped.sort_values(x_col)
    if top_n and len(grouped) > top_n:
        grouped = grouped.head(top_n)
    return [
        {x_col: _safe_val(r[x_col]), y_col: round(_safe_val(r[y_col]), 2) if _safe_val(r[y_col]) is not None else 0}
        for _, r in grouped.iterrows()
    ]


def _build_grouped_or_stacked_data(df, x_col, y_columns, aggregation="mean", top_n=None):
    agg_fn = aggregation if aggregation in ("mean", "sum", "count", "median", "min", "max") else "mean"
    valid_cols = [c for c in y_columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    if not valid_cols:
        return [], []
    if agg_fn == "count":
        grouped = df.groupby(x_col).size().reset_index(name="count")
        for c in valid_cols:
            grouped[c] = df.groupby(x_col)[c].count().values
    else:
        grouped = df.groupby(x_col)[valid_cols].agg(agg_fn).reset_index()
    if top_n and len(grouped) > top_n:
        total = grouped[valid_cols].sum(axis=1)
        grouped["_total"] = total
        grouped = grouped.sort_values("_total", ascending=False).head(top_n).drop(columns=["_total"])
    data = []
    for _, r in grouped.iterrows():
        row = {x_col: _safe_val(r[x_col])}
        for c in valid_cols:
            row[c] = round(_safe_val(r[c]), 2) if _safe_val(r[c]) is not None else 0
        data.append(row)
    return data, valid_cols


def _build_line_or_area_data(df, x_col, y_columns, top_n=None):
    valid_cols = [c for c in y_columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    if not valid_cols:
        return [], []
    sorted_df = df.sort_values(x_col)
    if top_n and len(sorted_df) > top_n:
        step = max(1, len(sorted_df) // top_n)
        sorted_df = sorted_df.iloc[::step]
    if len(sorted_df) > 200:
        step = max(1, len(sorted_df) // 200)
        sorted_df = sorted_df.iloc[::step]
    data = []
    for _, r in sorted_df.iterrows():
        row = {x_col: str(_safe_val(r[x_col]))}
        for c in valid_cols:
            val = _safe_val(r[c])
            row[c] = round(val, 2) if val is not None else None
        data.append(row)
    return data, valid_cols


def _build_histogram_data(df, col, bins=15):
    series = pd.to_numeric(df[col], errors="coerce").dropna()
    if series.empty:
        return []
    counts, edges = pd.cut(series, bins=min(bins, max(2, len(series))), retbins=True)
    hist = series.groupby(counts, observed=True).count()
    data_range = series.max() - series.min()
    use_int = data_range > 1 and series.dtype in ("int64", "Int64")
    result = []
    for iv, c in zip(hist.index, hist.values):
        if c > 0:
            if use_int:
                label = f"{int(round(iv.left))}-{int(round(iv.right))}"
            else:
                label = f"{iv.left:.2f}-{iv.right:.2f}"
            result.append({"bin": label, "count": int(c)})
    return result


def _build_scatter_data(df, x_col, y_col, max_points=200):
    clean = df[[x_col, y_col]].dropna()
    subset = clean.sample(n=min(max_points, len(clean)), random_state=42) if len(clean) > max_points else clean
    return [
        {x_col: _safe_val(r[x_col]), y_col: _safe_val(r[y_col])}
        for _, r in subset.iterrows()
    ]


def _build_pie_data(df, col, top_n=None):
    counts = df[col].value_counts()
    if top_n and len(counts) > top_n:
        top = counts.head(top_n)
        other_count = counts.iloc[top_n:].sum()
        if other_count > 0:
            top = pd.concat([top, pd.Series({"Other": other_count})])
        counts = top
    else:
        counts = counts.head(8)
    return [
        {"name": str(name), "value": int(count)}
        for name, count in counts.items()
    ]


def _compute_kpi_value(df, column, aggregation):
    if column not in df.columns:
        return None
    series = df[column]
    if aggregation == "count":
        return _safe_val(len(series.dropna()))
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return None
    ops = {"mean": series.mean, "median": series.median, "sum": series.sum, "min": series.min, "max": series.max}
    fn = ops.get(aggregation, series.mean)
    return _safe_val(fn())


def _build_chart_from_spec(df, chart_plan: dict) -> dict | None:
    chart_type = chart_plan.get("type", "bar")
    x_col = chart_plan.get("x_column", "")
    y_col = chart_plan.get("y_column", "")
    y_columns = chart_plan.get("y_columns", [])
    title = chart_plan.get("title", "Chart")
    aggregation = chart_plan.get("aggregation", "mean")
    top_n = chart_plan.get("top_n")
    sort_by = chart_plan.get("sort_by")
    bins = chart_plan.get("bins", 15)
    insight = chart_plan.get("insight", "")

    if x_col not in df.columns:
        return None

    if chart_type == "bar":
        if not y_col or y_col not in df.columns:
            return None
        data = _build_bar_data(df, x_col, y_col, aggregation, top_n, sort_by)
        if data:
            return {"type": "bar", "title": title, "x": x_col, "y": y_col, "data": data, "insight": insight}

    elif chart_type in ("grouped_bar", "stacked_bar"):
        if not y_columns:
            y_columns = [y_col] if y_col and y_col in df.columns else []
        data, series_keys = _build_grouped_or_stacked_data(df, x_col, y_columns, aggregation, top_n)
        if data and series_keys:
            return {"type": chart_type, "title": title, "x": x_col, "series": series_keys, "data": data, "insight": insight}

    elif chart_type in ("line", "area"):
        if not y_columns:
            y_columns = [y_col] if y_col and y_col in df.columns else []
        data, series_keys = _build_line_or_area_data(df, x_col, y_columns, top_n)
        if data and series_keys:
            return {"type": chart_type, "title": title, "x": x_col, "series": series_keys, "data": data, "insight": insight}

    elif chart_type == "histogram":
        data = _build_histogram_data(df, x_col, bins)
        if data:
            return {"type": "histogram", "title": title, "x": "bin", "y": "count", "data": data, "insight": insight}

    elif chart_type == "scatter":
        if not y_col or y_col not in df.columns:
            return None
        data = _build_scatter_data(df, x_col, y_col)
        if data:
            return {"type": "scatter", "title": title, "x": x_col, "y": y_col, "data": data, "insight": insight}

    elif chart_type == "pie":
        data = _build_pie_data(df, x_col, top_n)
        if data:
            return {"type": "pie", "title": title, "x": "name", "y": "value", "data": data, "insight": insight}

    return None


# ---------------------------------------------------------------------------
# Feature importance (SHAP aggregation)
# ---------------------------------------------------------------------------

def _aggregate_onehot_features(features: list[dict]) -> list[dict]:
    names = [f["feature"] for f in features]
    prefix_counts: dict[str, int] = {}
    for name in names:
        parts = name.split("_")
        for i in range(1, len(parts)):
            prefix = "_".join(parts[:i])
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    onehot_prefixes: set[str] = set()
    for prefix, count in sorted(prefix_counts.items(), key=lambda x: -len(x[0])):
        if count >= 2 and not any(p.startswith(prefix + "_") for p in onehot_prefixes):
            onehot_prefixes.add(prefix)
    aggregated: dict[str, float] = {}
    for f in features:
        name = f["feature"]
        imp = f["importance"]
        matched = False
        for prefix in sorted(onehot_prefixes, key=len, reverse=True):
            if name.startswith(prefix + "_") or name == prefix:
                aggregated[prefix] = aggregated.get(prefix, 0) + imp
                matched = True
                break
        if not matched:
            aggregated[name] = aggregated.get(name, 0) + imp
    return [{"feature": k, "importance": v} for k, v in aggregated.items()]


def _clean_feature_name(name: str) -> str:
    parts = name.split("_")
    seen = set()
    deduped = []
    for p in parts:
        low = p.lower()
        if low not in seen:
            seen.add(low)
            deduped.append(p)
    name = " ".join(deduped)
    name = name.strip()
    if name.lower() == name:
        name = name.title()
    return name


def _build_feature_importance_chart(shap_summary: dict, model_metrics: dict) -> dict | None:
    features = shap_summary.get("feature_importance", [])
    if not features:
        return None
    task = model_metrics.get("task", "regression")
    target = model_metrics.get("target", "target")
    score_key = "accuracy" if task == "classification" else "r2_score"
    score_val = model_metrics.get(score_key, 0)
    agg = _aggregate_onehot_features(features)
    agg.sort(key=lambda x: x["importance"], reverse=True)
    data = [
        {"feature": _clean_feature_name(f["feature"]), "importance": round(f["importance"], 4)}
        for f in agg[:10]
    ]
    data.reverse()
    score_pct = f"{score_val * 100:.0f}%"
    score_label = "accuracy" if task == "classification" else "R² score"
    target_label = target.replace("_", " ").title()
    return {
        "type": "feature_importance",
        "title": f"What Drives {target_label}?",
        "x": "importance",
        "y": "feature",
        "data": data,
        "insight": f"Top factors influencing {target_label.lower()} predictions ({score_pct} {score_label}). Longer bars = stronger influence.",
    }


# ---------------------------------------------------------------------------
# LLM story generation
# ---------------------------------------------------------------------------

async def _llm_design_story(
    profiles: list[dict],
    correlations: dict,
    outliers: dict,
    eda_summary: dict,
    cleaning_report: dict,
    row_count: int,
    col_count: int,
    domain: str,
) -> dict | None:
    from packages.agents.llm import get_llm, is_llm_available

    if not is_llm_available():
        return None

    try:
        llm = get_llm(temperature=0.3)

        strong_pairs = correlations.get("strong_pairs", [])
        corr_text = "No strong correlations." if not strong_pairs else "\n".join(
            f"  {p['col1']} <-> {p['col2']}: r={p['correlation']:.3f}" for p in strong_pairs[:10]
        )
        outlier_text = "No outliers." if not outliers else "\n".join(
            f"  {col}: {info.get('count', 0)} outliers" for col, info in outliers.items()
        )

        ai_analysis = eda_summary.get("ai_analysis", {})
        insights_text = "No AI insights available."
        if ai_analysis:
            insights = ai_analysis.get("key_insights", [])
            story = ai_analysis.get("data_story", "")
            insights_text = story + "\n" + "\n".join(f"- {i}" for i in insights)

        cleaning_summary = cleaning_report.get("ai_notes", "")
        if not cleaning_summary:
            cleaning_summary = (
                f"Rows: {cleaning_report.get('rows_after_cleaning', row_count)}, "
                f"Cols: {cleaning_report.get('columns_after_cleaning', col_count)}, "
                f"Duplicates removed: {cleaning_report.get('duplicates', {}).get('duplicates_found', 0)}"
            )

        prompt = STORY_PROMPT.format(
            domain=domain,
            domain_description=DOMAIN_DESCRIPTIONS.get(domain, "General"),
            row_count=row_count,
            col_count=col_count,
            profiles_text=_profiles_to_text(profiles),
            correlations_text=corr_text,
            outliers_text=outlier_text,
            insights_text=insights_text,
            cleaning_summary=cleaning_summary,
        )

        response = await llm.ainvoke(prompt)
        text = response.content.strip()
        if text.startswith("```"):
            parts = text.split("\n", 1)
            text = parts[1] if len(parts) > 1 else parts[0][3:]
            text = text.rsplit("```", 1)[0].strip()

        plan = json.loads(text)
        logger.info("LLM story plan: hero=%s", plan.get("hero", {}).get("headline", ""))
        return plan
    except Exception as e:
        logger.warning("LLM story design failed, falling back: %s", e)
        return None


# ---------------------------------------------------------------------------
# Static fallback (no LLM)
# ---------------------------------------------------------------------------

def _static_story_fallback(df, profiles, correlations, outliers, cleaning_report):
    numeric_cols = [p for p in profiles if p.get("mean") is not None]
    categorical_cols = [
        p for p in profiles
        if p.get("mean") is None and not p.get("is_id_column") and not p.get("is_datetime")
    ]

    hero_col = numeric_cols[0] if numeric_cols else None
    hero = {
        "headline": f"Analysis of {len(df)} records across {len(df.columns)} dimensions" if df is not None else "Dataset Analysis",
        "big_number": f"{len(df):,}" if df is not None else "0",
        "big_number_label": "Total Records",
        "big_number_context": f"with {len(numeric_cols)} numeric and {len(categorical_cols)} categorical columns",
        "summary": "Upload analyzed successfully. See the charts below for key patterns in your data.",
    }

    insights = []
    for p in numeric_cols[:3]:
        col = p["column_name"]
        label = col.replace("_", " ").title()
        insights.append({
            "finding": f"Average {label} is {p['mean']:.2f}",
            "detail": f"Ranges from {p.get('min', 'N/A')} to {p.get('max', 'N/A')}",
            "sentiment": "neutral",
            "metric_value": f"{p['mean']:.1f}",
            "metric_label": f"Avg {label}",
        })

    story_sections = []
    if categorical_cols and numeric_cols and df is not None:
        cat, num = categorical_cols[0], numeric_cols[0]
        chart = _build_chart_from_spec(df, {
            "type": "bar", "title": f"{num['column_name'].replace('_', ' ').title()} by {cat['column_name'].replace('_', ' ').title()}",
            "x_column": cat["column_name"], "y_column": num["column_name"],
            "aggregation": "mean", "top_n": 10, "sort_by": "value",
        })
        if chart:
            story_sections.append({
                "title": f"How {cat['column_name'].replace('_', ' ').title()} Affects {num['column_name'].replace('_', ' ').title()}",
                "narrative": f"Breaking down {num['column_name'].replace('_', ' ')} by {cat['column_name'].replace('_', ' ')} reveals differences across categories.",
                "chart": chart,
            })

    if df is not None and numeric_cols:
        col = numeric_cols[0]["column_name"]
        chart = _build_chart_from_spec(df, {
            "type": "histogram", "title": f"Distribution of {col.replace('_', ' ').title()}",
            "x_column": col, "bins": 15,
        })
        if chart:
            story_sections.append({
                "title": f"Understanding the Spread of {col.replace('_', ' ').title()}",
                "narrative": f"The distribution of {col.replace('_', ' ')} shows where most values fall and where outliers exist.",
                "chart": chart,
            })

    kpis = []
    for p in numeric_cols[:4]:
        kpis.append({
            "label": p["column_name"].replace("_", " ").title(),
            "value": round(p["mean"], 2) if p["mean"] is not None else 0,
        })

    recommendations = [
        "Review the data quality section below for potential issues",
        "Investigate any outlier patterns that may affect your analysis",
    ]

    return {
        "hero": hero,
        "insights": insights,
        "story_sections": story_sections,
        "recommendations": recommendations,
        "kpis": kpis,
        "charts": [],
    }


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def dashboard_builder_node(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.store import ArtifactStore, JobStepManager

    run_id = state["run_id"]
    jsm = JobStepManager(db_session)

    if await jsm.is_completed(run_id, "dashboard_builder"):
        logger.info("dashboard_builder already completed, skipping")
        store = ArtifactStore(db_session)
        cached = await store.get(run_id, "dashboard_spec")
        if cached:
            state["dashboard_spec"] = cached
        return state

    await jsm.start_step(run_id, "dashboard_builder")
    try:
        profiles = state.get("column_profiles", [])
        correlations = state.get("correlations", {})
        outliers = state.get("outliers", {})
        cleaning_report = state.get("cleaning_report", {})
        eda_summary = state.get("eda_summary", {})

        cleaned_uri = state.get("cleaned_storage_uri")
        encoding = state.get("detected_encoding", "utf-8")
        df = None
        if cleaned_uri:
            raw = storage.get(cleaned_uri)
            df = pd.read_csv(io.BytesIO(raw), encoding=encoding)

        domain = _detect_domain(profiles)

        story_plan = await _llm_design_story(
            profiles, correlations, outliers, eda_summary, cleaning_report,
            row_count=len(df) if df is not None else 0,
            col_count=len(df.columns) if df is not None else 0,
            domain=domain,
        )

        if story_plan and df is not None:
            # Build KPI values
            kpis = []
            for kpi_plan in story_plan.get("kpis", []):
                val = _compute_kpi_value(df, kpi_plan.get("column", ""), kpi_plan.get("aggregation", "mean"))
                if val is not None:
                    kpi_entry = {"label": kpi_plan.get("label", ""), "value": val}
                    if kpi_plan.get("format"):
                        kpi_entry["format"] = kpi_plan["format"]
                    if kpi_plan.get("comparison_text"):
                        kpi_entry["comparison_text"] = kpi_plan["comparison_text"]
                    kpis.append(kpi_entry)

            # Build story section charts
            story_sections = []
            for section in story_plan.get("story_sections", []):
                chart_plan = section.get("chart", {})
                chart = _build_chart_from_spec(df, chart_plan) if chart_plan else None
                story_sections.append({
                    "title": section.get("title", ""),
                    "narrative": section.get("narrative", ""),
                    "chart": chart,
                })

            # Build extra charts for deep dive
            extra_charts = []
            missing_cols = [p for p in profiles if p.get("missing_count", 0) > 0]
            strong_pairs = correlations.get("strong_pairs", [])

            # Feature importance
            shap_summary = state.get("shap_summary")
            model_metrics = state.get("model_metrics")
            fi_chart = None
            if shap_summary and model_metrics:
                fi_chart = _build_feature_importance_chart(shap_summary, model_metrics)

            spec = {
                "spec_version": "4.0",
                "dataset_id": state.get("dataset_id", ""),
                "run_id": run_id,
                "domain": domain,
                "hero": story_plan.get("hero", {}),
                "insights": story_plan.get("insights", []),
                "story_sections": story_sections,
                "recommendations": story_plan.get("recommendations", []),
                "kpis": kpis,
                "charts": extra_charts,
                "data_quality": {
                    "rows_total": cleaning_report.get("rows_after_cleaning", 0),
                    "columns_total": cleaning_report.get("columns_after_cleaning", 0),
                    "duplicates_removed": cleaning_report.get("duplicates", {}).get("duplicates_found", 0),
                    "columns_with_missing": len(missing_cols),
                    "columns_with_outliers": len(outliers),
                },
                "correlations_summary": {
                    "strong_pair_count": len(strong_pairs),
                    "top_pairs": strong_pairs[:5],
                },
                "model_metrics": model_metrics if model_metrics else None,
                "feature_importance_chart": fi_chart,
                "ai_driven": True,
            }
        else:
            # Fallback without LLM
            fallback = _static_story_fallback(df, profiles, correlations, outliers, cleaning_report)
            strong_pairs = correlations.get("strong_pairs", [])

            shap_summary = state.get("shap_summary")
            model_metrics = state.get("model_metrics")
            fi_chart = None
            if shap_summary and model_metrics:
                fi_chart = _build_feature_importance_chart(shap_summary, model_metrics)

            spec = {
                "spec_version": "4.0",
                "dataset_id": state.get("dataset_id", ""),
                "run_id": run_id,
                "domain": domain,
                **fallback,
                "data_quality": {
                    "rows_total": cleaning_report.get("rows_after_cleaning", 0),
                    "columns_total": cleaning_report.get("columns_after_cleaning", 0),
                    "duplicates_removed": cleaning_report.get("duplicates", {}).get("duplicates_found", 0),
                    "columns_with_missing": len([p for p in profiles if p.get("missing_count", 0) > 0]),
                    "columns_with_outliers": len(outliers),
                },
                "correlations_summary": {
                    "strong_pair_count": len(strong_pairs),
                    "top_pairs": strong_pairs[:5],
                },
                "model_metrics": model_metrics if model_metrics else None,
                "feature_importance_chart": fi_chart,
                "ai_driven": False,
            }

        spec_json = json.dumps(spec).encode()
        spec_key = f"datasets/{state.get('dataset_id', 'unknown')}/dashboard_spec.json"
        storage.put(spec_key, spec_json)

        store = ArtifactStore(db_session)
        await store.put(run_id, "dashboard_builder", "dashboard_spec", spec)

        state["dashboard_spec"] = spec
        state["dashboard_spec_uri"] = spec_key
        state["current_node"] = "dashboard_builder"
        state["status"] = "completed"

        await jsm.end_step(run_id, "dashboard_builder", "succeeded")
        logger.info(
            "dashboard_builder completed (domain=%s, ai=%s): %d insights, %d story sections",
            domain, spec.get("ai_driven", False),
            len(spec.get("insights", [])), len(spec.get("story_sections", [])),
        )
    except Exception as e:
        await jsm.end_step(run_id, "dashboard_builder", "failed", str(e))
        state["error"] = str(e)
        state["status"] = "failed"
        raise

    return state
