import csv
import io
import json
import secrets
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import delete, select

from apps.api.config import settings
from apps.api.deps import CurrentUserId, DbSession
from packages.db.models import (
    AnalysisRun,
    Artifact,
    ColumnProfile,
    Dataset,
    JobStep,
    ToolCall,
)
from packages.security.file_validator import validate_file
from packages.security.malware_scanner import scan_file
from packages.storage.local import LocalDiskStore

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


async def _get_user_dataset(db, dataset_id: str, user_id: str) -> Dataset:
    result = await db.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id, Dataset.user_id == user_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(404, detail="Dataset not found")
    return dataset


@router.get("")
async def list_datasets(db: DbSession, user_id: CurrentUserId):
    latest_run_subq = (
        select(
            AnalysisRun.dataset_id,
            AnalysisRun.run_id,
            AnalysisRun.status,
            AnalysisRun.completed_at,
        )
        .distinct(AnalysisRun.dataset_id)
        .order_by(AnalysisRun.dataset_id, AnalysisRun.created_at.desc())
        .subquery()
    )

    result = await db.execute(
        select(Dataset, latest_run_subq)
        .outerjoin(latest_run_subq, Dataset.dataset_id == latest_run_subq.c.dataset_id)
        .where(Dataset.user_id == user_id)
        .order_by(Dataset.created_at.desc())
    )
    rows = result.all()

    items = []
    for row in rows:
        d = row[0]
        run_id = row[1] if len(row) > 1 else None
        run_status = row[2] if len(row) > 2 else None
        run_completed = row[3] if len(row) > 3 else None

        latest_run = None
        if run_id is not None:
            latest_run = {
                "run_id": str(run_id),
                "status": run_status,
                "completed_at": run_completed.isoformat() if run_completed else None,
            }

        items.append({
            "dataset_id": str(d.dataset_id),
            "filename": d.original_filename,
            "row_count": d.row_count,
            "column_count": d.column_count,
            "status": d.status,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else d.created_at.isoformat(),
            "latest_run": latest_run,
        })

    return items


def _get_storage() -> LocalDiskStore:
    return LocalDiskStore(settings.STORAGE_LOCAL_ROOT)


@router.post("/upload")
async def upload_dataset(
    file: UploadFile,
    db: DbSession,
    user_id: CurrentUserId,
):
    content = await file.read()
    filename = file.filename or "upload.csv"

    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

    malware_result = scan_file(content, filename)
    if not malware_result["safe"]:
        raise HTTPException(400, detail=malware_result["error"])

    file_result = validate_file(content, filename)
    if not file_result["valid"]:
        raise HTTPException(400, detail=file_result["error"])

    dataset_id = str(uuid.uuid4())
    storage_key = f"datasets/{dataset_id}/raw.csv"

    storage = _get_storage()
    storage.put(storage_key, content)

    dataset = Dataset(
        dataset_id=dataset_id,
        user_id=user_id,
        original_filename=filename,
        storage_uri=storage_key,
        file_size_bytes=len(content),
        row_count=file_result.get("row_count"),
        column_count=file_result.get("column_count"),
        detected_encoding=file_result.get("encoding", "utf-8"),
        status="uploaded",
    )
    db.add(dataset)
    await db.commit()

    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "size_bytes": len(content),
        "row_count": file_result.get("row_count"),
        "column_count": file_result.get("column_count"),
        "status": "uploaded",
    }


@router.post("/{dataset_id}/analyze")
async def analyze_dataset(
    dataset_id: str,
    db: DbSession,
    user_id: CurrentUserId,
    background_tasks: BackgroundTasks,
):
    dataset = await _get_user_dataset(db, dataset_id, user_id)

    active_run = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.dataset_id == dataset_id,
            AnalysisRun.status.in_(["pending", "running"]),
        )
    )
    if active_run.scalar_one_or_none():
        raise HTTPException(409, detail="An analysis is already running for this dataset")

    run_id = str(uuid.uuid4())
    run = AnalysisRun(
        run_id=run_id,
        dataset_id=dataset_id,
        status="pending",
    )
    db.add(run)
    await db.commit()

    async def _run_in_background():
        from apps.api.db import async_session
        async with async_session() as session:
            from apps.worker.run_pipeline import execute_pipeline
            await execute_pipeline(
                dataset_id=dataset_id,
                run_id=run_id,
                storage_uri=dataset.storage_uri,
                original_filename=dataset.original_filename,
                detected_encoding=dataset.detected_encoding or "utf-8",
                user_id=str(user_id),
                db_session=session,
            )

    background_tasks.add_task(_run_in_background)

    return {"run_id": run_id, "dataset_id": dataset_id, "status": "pending"}


@router.get("/{dataset_id}/runs")
async def list_runs(dataset_id: str, db: DbSession, user_id: CurrentUserId):
    await _get_user_dataset(db, dataset_id, user_id)

    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.dataset_id == dataset_id)
        .order_by(AnalysisRun.created_at.desc())
    )
    runs = result.scalars().all()
    return [
        {
            "run_id": str(r.run_id),
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "processing_time_seconds": (
                float(r.processing_time_seconds) if r.processing_time_seconds else None
            ),
            "error_message": r.error_message,
        }
        for r in runs
    ]


@router.get("/{dataset_id}/runs/{run_id}/status")
async def get_run_status(dataset_id: str, run_id: str, db: DbSession, user_id: CurrentUserId):
    await _get_user_dataset(db, dataset_id, user_id)

    result = await db.execute(
        select(AnalysisRun).where(
            AnalysisRun.run_id == run_id, AnalysisRun.dataset_id == dataset_id
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, detail="Run not found")

    steps_result = await db.execute(
        select(JobStep).where(JobStep.run_id == run_id).order_by(JobStep.started_at)
    )
    steps = steps_result.scalars().all()

    return {
        "run_id": str(run.run_id),
        "dataset_id": str(run.dataset_id),
        "status": run.status,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "processing_time_seconds": (
            float(run.processing_time_seconds) if run.processing_time_seconds else None
        ),
        "steps": [
            {
                "node": s.node_name,
                "status": s.status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
            for s in steps
        ],
    }


@router.get("/{dataset_id}/dashboard")
async def get_dashboard(dataset_id: str, db: DbSession, user_id: CurrentUserId):
    await _get_user_dataset(db, dataset_id, user_id)

    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.dataset_id == dataset_id, AnalysisRun.status == "completed")
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, detail="No completed analysis found for this dataset")

    if not run.dashboard_spec_uri:
        raise HTTPException(404, detail="Dashboard spec not available")

    storage = _get_storage()
    try:
        spec_bytes = storage.get(run.dashboard_spec_uri)
        spec = json.loads(spec_bytes)
    except FileNotFoundError:
        raise HTTPException(404, detail="Dashboard spec file not found")

    profiles_result = await db.execute(
        select(ColumnProfile).where(ColumnProfile.run_id == str(run.run_id))
    )
    profiles = profiles_result.scalars().all()

    return {
        "dashboard_spec": spec,
        "column_profiles": [
            {
                "column_name": p.column_name,
                "dtype": p.dtype,
                "missing_count": p.missing_count,
                "missing_pct": float(p.missing_pct) if p.missing_pct is not None else None,
                "unique_count": p.unique_count,
                "mean": float(p.mean) if p.mean is not None else None,
                "std": float(p.std) if p.std is not None else None,
                "min": float(p.min) if p.min is not None else None,
                "max": float(p.max) if p.max is not None else None,
                "has_outliers": p.has_outliers,
            }
            for p in profiles
        ],
        "run_id": str(run.run_id),
    }


@router.get("/{dataset_id}/preview")
async def preview_dataset(dataset_id: str, db: DbSession, user_id: CurrentUserId):
    dataset = await _get_user_dataset(db, dataset_id, user_id)

    storage = _get_storage()
    try:
        raw = storage.get(dataset.storage_uri)
    except FileNotFoundError:
        raise HTTPException(404, detail="CSV file not found")

    encoding = dataset.detected_encoding or "utf-8"
    text = raw.decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    columns = reader.fieldnames or []
    rows = []
    for i, row in enumerate(reader):
        if i >= 50:
            break
        rows.append(row)

    return {
        "columns": columns,
        "rows": rows,
        "total_rows": dataset.row_count,
        "total_columns": dataset.column_count,
    }


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str, db: DbSession, user_id: CurrentUserId):
    dataset = await _get_user_dataset(db, dataset_id, user_id)

    storage = _get_storage()

    runs_result = await db.execute(
        select(AnalysisRun).where(AnalysisRun.dataset_id == dataset_id)
    )
    runs = runs_result.scalars().all()
    run_ids = [str(r.run_id) for r in runs]

    for r in runs:
        for uri in (r.cleaned_data_uri, r.model_uri, r.shap_uri, r.dashboard_spec_uri):
            if uri:
                try:
                    storage.delete(uri)
                except Exception:
                    pass

    if run_ids:
        await db.execute(delete(ColumnProfile).where(ColumnProfile.run_id.in_(run_ids)))
        await db.execute(delete(ToolCall).where(ToolCall.run_id.in_(run_ids)))
        await db.execute(delete(Artifact).where(Artifact.run_id.in_(run_ids)))
        await db.execute(delete(JobStep).where(JobStep.run_id.in_(run_ids)))
        await db.execute(delete(AnalysisRun).where(AnalysisRun.dataset_id == dataset_id))

    try:
        storage.delete(dataset.storage_uri)
    except Exception:
        pass

    await db.delete(dataset)
    await db.commit()
    return {"deleted": True}


@router.post("/{dataset_id}/share")
async def share_dataset(dataset_id: str, db: DbSession, user_id: CurrentUserId):
    dataset = await _get_user_dataset(db, dataset_id, user_id)

    if not dataset.share_token:
        dataset.share_token = secrets.token_urlsafe(16)
        await db.commit()

    return {"share_token": dataset.share_token}


@router.delete("/{dataset_id}/share")
async def unshare_dataset(dataset_id: str, db: DbSession, user_id: CurrentUserId):
    dataset = await _get_user_dataset(db, dataset_id, user_id)

    dataset.share_token = None
    await db.commit()
    return {"unshared": True}


# --- Public shared dashboard (no auth required) ---

shared_router = APIRouter(prefix="/api/shared", tags=["shared"])


@shared_router.get("/{share_token}/dashboard")
async def get_shared_dashboard(share_token: str, db: DbSession):
    result = await db.execute(
        select(Dataset).where(Dataset.share_token == share_token)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(404, detail="Shared dashboard not found")

    run_result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.dataset_id == str(dataset.dataset_id), AnalysisRun.status == "completed")
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    run = run_result.scalar_one_or_none()
    if not run or not run.dashboard_spec_uri:
        raise HTTPException(404, detail="No completed analysis for this shared dataset")

    storage = _get_storage()
    try:
        spec_bytes = storage.get(run.dashboard_spec_uri)
        spec = json.loads(spec_bytes)
    except FileNotFoundError:
        raise HTTPException(404, detail="Dashboard spec file not found")

    return {
        "dashboard_spec": spec,
        "filename": dataset.original_filename,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
    }
