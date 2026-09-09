import io
import logging

import pandas as pd

from packages.agents.state import AgentState
from packages.security.csv_injection_guard import check_csv_injection
from packages.security.file_validator import validate_file
from packages.security.malware_scanner import scan_file
from packages.security.pii_detector import detect_pii

logger = logging.getLogger("cortexbi.agents.nodes.validation")


async def validation_node(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.store import ArtifactStore, JobStepManager

    run_id = state["run_id"]
    jsm = JobStepManager(db_session)

    if await jsm.is_completed(run_id, "validation"):
        logger.info("validation already completed, skipping")
        store = ArtifactStore(db_session)
        cached = await store.get(run_id, "validation_report")
        if cached:
            state["validation_report"] = cached
            state["is_valid"] = cached.get("is_valid", True)
        return state

    await jsm.start_step(run_id, "validation")
    try:
        raw = storage.get(state["raw_storage_uri"])
        filename = state.get("original_filename", "upload.csv")
        encoding = state.get("detected_encoding", "utf-8")

        malware_result = scan_file(raw, filename)
        file_result = validate_file(raw, filename)
        df = pd.read_csv(io.BytesIO(raw), encoding=encoding)
        injection_result = check_csv_injection(df)
        pii_result = detect_pii(df)

        if not injection_result["safe"]:
            logger.info(
                "csv injection-like prefixes in %d columns (harmless for analytics): %s",
                len(injection_result["columns"]), injection_result["columns"],
            )

        is_valid = malware_result["safe"] and file_result["valid"]

        report = {
            "is_valid": is_valid,
            "malware_scan": malware_result,
            "file_validation": file_result,
            "csv_injection": injection_result,
            "pii_detection": pii_result,
        }

        store = ArtifactStore(db_session)
        await store.put(run_id, "validation", "validation_report", report)

        state["validation_report"] = report
        state["is_valid"] = is_valid
        state["current_node"] = "validation"

        if not is_valid:
            errors = []
            if not malware_result["safe"]:
                errors.append(malware_result.get("error", "Malware detected"))
            if not file_result["valid"]:
                errors.append(file_result.get("error", "File validation failed"))
            state["error"] = "; ".join(errors)
            state["status"] = "failed"
            await jsm.end_step(run_id, "validation", "failed", state["error"])
        else:
            await jsm.end_step(run_id, "validation", "succeeded")
            logger.info("validation passed")
    except Exception as e:
        await jsm.end_step(run_id, "validation", "failed", str(e))
        state["error"] = str(e)
        state["status"] = "failed"
        raise

    return state
