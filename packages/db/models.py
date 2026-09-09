import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    datasets: Mapped[list["Dataset"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Dataset(Base):
    __tablename__ = "datasets"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer)
    column_count: Mapped[int | None] = mapped_column(Integer)
    detected_encoding: Mapped[str | None] = mapped_column(Text, default="utf-8")
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="uploaded"
    )
    share_token: Mapped[str | None] = mapped_column(Text, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="datasets")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'analyzing', 'completed', 'failed')",
            name="ck_datasets_status",
        ),
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.dataset_id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    processing_time_seconds: Mapped[float | None] = mapped_column(Numeric)
    ml_task: Mapped[str | None] = mapped_column(Text)
    ml_target: Mapped[str | None] = mapped_column(Text)
    model_accuracy: Mapped[float | None] = mapped_column(Numeric)
    model_r2_score: Mapped[float | None] = mapped_column(Numeric)
    cleaned_data_uri: Mapped[str | None] = mapped_column(Text)
    model_uri: Mapped[str | None] = mapped_column(Text)
    shap_uri: Mapped[str | None] = mapped_column(Text)
    dashboard_spec_uri: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    dataset: Mapped["Dataset"] = relationship(back_populates="analysis_runs")
    job_steps: Mapped[list["JobStep"]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")
    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")
    column_profiles: Mapped[list["ColumnProfile"]] = relationship(back_populates="analysis_run", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_analysis_runs_status",
        ),
    )


class JobStep(Base):
    __tablename__ = "job_steps"

    job_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="job_steps")

    __table_args__ = (
        UniqueConstraint("run_id", "node_name", name="uq_job_steps_run_node"),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'skipped')",
            name="ck_job_steps_status",
        ),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="artifacts")

    __table_args__ = (
        UniqueConstraint("run_id", "type", "version", name="uq_artifacts_run_type_version"),
    )


class ToolCall(Base):
    __tablename__ = "tool_calls"

    tool_call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    tool_input: Mapped[dict | None] = mapped_column(JSONB)
    tool_output: Mapped[dict | None] = mapped_column(JSONB)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="tool_calls")

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'error')",
            name="ck_tool_calls_status",
        ),
    )


class ColumnProfile(Base):
    __tablename__ = "column_profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_name: Mapped[str] = mapped_column(Text, nullable=False)
    dtype: Mapped[str] = mapped_column(Text, nullable=False)
    missing_count: Mapped[int | None] = mapped_column(Integer)
    missing_pct: Mapped[float | None] = mapped_column(Numeric)
    unique_count: Mapped[int | None] = mapped_column(Integer)
    unique_pct: Mapped[float | None] = mapped_column(Numeric)
    mean: Mapped[float | None] = mapped_column(Numeric)
    std: Mapped[float | None] = mapped_column(Numeric)
    min: Mapped[float | None] = mapped_column(Numeric)
    max: Mapped[float | None] = mapped_column(Numeric)
    q25: Mapped[float | None] = mapped_column(Numeric)
    q50: Mapped[float | None] = mapped_column(Numeric)
    q75: Mapped[float | None] = mapped_column(Numeric)
    top_values: Mapped[dict | None] = mapped_column(JSONB)
    is_id_column: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_datetime: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_outliers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    analysis_run: Mapped["AnalysisRun"] = relationship(back_populates="column_profiles")

    __table_args__ = (
        UniqueConstraint("run_id", "column_name", name="uq_column_profiles_run_column"),
    )
