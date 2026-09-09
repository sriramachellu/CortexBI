"""audit fixes: cascades, indexes, new columns, constraints

Revision ID: a3f7b2c91d04
Revises: 2513fe199c88
Create Date: 2026-09-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f7b2c91d04"
down_revision: Union[str, None] = "2513fe199c88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("detected_encoding", sa.Text(), nullable=True))
    op.execute("UPDATE datasets SET detected_encoding = 'utf-8' WHERE detected_encoding IS NULL")

    op.add_column("analysis_runs", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE analysis_runs SET updated_at = created_at WHERE updated_at IS NULL")

    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    op.create_index("ix_job_steps_run_id", "job_steps", ["run_id"])
    op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"])

    op.create_unique_constraint("uq_column_profiles_run_column", "column_profiles", ["run_id", "column_name"])

    op.drop_constraint("datasets_user_id_fkey", "datasets", type_="foreignkey")
    op.create_foreign_key("datasets_user_id_fkey", "datasets", "users", ["user_id"], ["user_id"], ondelete="CASCADE")

    op.drop_constraint("analysis_runs_dataset_id_fkey", "analysis_runs", type_="foreignkey")
    op.create_foreign_key("analysis_runs_dataset_id_fkey", "analysis_runs", "datasets", ["dataset_id"], ["dataset_id"], ondelete="CASCADE")

    op.drop_constraint("job_steps_run_id_fkey", "job_steps", type_="foreignkey")
    op.create_foreign_key("job_steps_run_id_fkey", "job_steps", "analysis_runs", ["run_id"], ["run_id"], ondelete="CASCADE")

    op.drop_constraint("artifacts_run_id_fkey", "artifacts", type_="foreignkey")
    op.create_foreign_key("artifacts_run_id_fkey", "artifacts", "analysis_runs", ["run_id"], ["run_id"], ondelete="CASCADE")

    op.drop_constraint("tool_calls_run_id_fkey", "tool_calls", type_="foreignkey")
    op.create_foreign_key("tool_calls_run_id_fkey", "tool_calls", "analysis_runs", ["run_id"], ["run_id"], ondelete="CASCADE")

    op.drop_constraint("column_profiles_run_id_fkey", "column_profiles", type_="foreignkey")
    op.create_foreign_key("column_profiles_run_id_fkey", "column_profiles", "analysis_runs", ["run_id"], ["run_id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("column_profiles_run_id_fkey", "column_profiles", type_="foreignkey")
    op.create_foreign_key("column_profiles_run_id_fkey", "column_profiles", "analysis_runs", ["run_id"], ["run_id"])

    op.drop_constraint("tool_calls_run_id_fkey", "tool_calls", type_="foreignkey")
    op.create_foreign_key("tool_calls_run_id_fkey", "tool_calls", "analysis_runs", ["run_id"], ["run_id"])

    op.drop_constraint("artifacts_run_id_fkey", "artifacts", type_="foreignkey")
    op.create_foreign_key("artifacts_run_id_fkey", "artifacts", "analysis_runs", ["run_id"], ["run_id"])

    op.drop_constraint("job_steps_run_id_fkey", "job_steps", type_="foreignkey")
    op.create_foreign_key("job_steps_run_id_fkey", "job_steps", "analysis_runs", ["run_id"], ["run_id"])

    op.drop_constraint("analysis_runs_dataset_id_fkey", "analysis_runs", type_="foreignkey")
    op.create_foreign_key("analysis_runs_dataset_id_fkey", "analysis_runs", "datasets", ["dataset_id"], ["dataset_id"])

    op.drop_constraint("datasets_user_id_fkey", "datasets", type_="foreignkey")
    op.create_foreign_key("datasets_user_id_fkey", "datasets", "users", ["user_id"], ["user_id"])

    op.drop_constraint("uq_column_profiles_run_column", "column_profiles", type_="unique")

    op.drop_index("ix_artifacts_run_id", table_name="artifacts")
    op.drop_index("ix_job_steps_run_id", table_name="job_steps")
    op.drop_index("ix_analysis_runs_status", table_name="analysis_runs")

    op.drop_column("analysis_runs", "updated_at")
    op.drop_column("datasets", "detected_encoding")
