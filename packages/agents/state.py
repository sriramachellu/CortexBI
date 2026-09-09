from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    dataset_id: str
    user_id: str

    # Input
    raw_storage_uri: str
    original_filename: str
    detected_encoding: str

    # Validation
    validation_report: dict
    is_valid: bool

    # Cleaning
    cleaned_storage_uri: str
    cleaning_report: dict

    # EDA
    column_profiles: list[dict]
    correlations: dict
    outliers: dict
    eda_summary: dict

    # Dashboard
    dashboard_spec: dict
    dashboard_spec_uri: str

    # ML (Phase 2)
    ml_task: str
    ml_target: str
    model_uri: str
    model_metrics: dict
    shap_uri: str
    shap_summary: dict

    # Control
    current_node: str
    status: str
    error: str
    tool_call_log: list[dict]
