"""Add nullable scheduled-task dispatch fields.

Revision ID: c8e4f2a6b901
Revises: nf12ab34cd56

Deploy before consumers; reserve status 6 until all readers support starting.
Downgrade requires stopping new writers and reconciling starting runs, and
otherwise discards the new fields. Older binaries require a compatible revision.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import VARCHAR

from omnigent.db.db_models import Uuid16

revision: str = "c8e4f2a6b901"
down_revision: str | None = "nf12ab34cd56"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def _byte_length(column: str) -> sa.ColumnElement:
    value = sa.column(column)
    if op.get_bind().dialect.name == "sqlite":
        return sa.func.length(sa.cast(value, sa.LargeBinary()))
    if op.get_bind().dialect.name == "cloudflare_d1":
        # D1 compiles LargeBinary as TEXT; BLOB is required to count UTF-8 bytes.
        return sa.literal_column(f"length(CAST({column} AS BLOB))")
    return sa.func.octet_length(value)


def upgrade() -> None:
    """Add nullable dispatch fields, occurrence uniqueness, and scan indexes."""
    with op.batch_alter_table("scheduled_tasks") as batch:
        batch.add_column(sa.Column("next_run_at", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("project_id", Uuid16(), nullable=True))
        batch.add_column(sa.Column("delegation_ref", sa.String(1024), nullable=True))
        batch.create_check_constraint(
            "ck_scheduled_tasks_delegation_ref_size", _byte_length("delegation_ref") <= 1024
        )
        batch.create_index(
            "ix_scheduled_tasks_due", ["state", "next_run_at", "workspace_id", "id"]
        )

    with op.batch_alter_table("scheduled_task_runs") as batch:
        batch.add_column(
            sa.Column(
                "trigger_key",
                sa.String(256).with_variant(
                    VARCHAR(256, charset="utf8mb4", collation="utf8mb4_bin"), "mysql"
                ),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("host_id", Uuid16(), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.BigInteger(), nullable=True))
        batch.create_check_constraint(
            "ck_scheduled_task_runs_trigger_key_size", _byte_length("trigger_key") <= 256
        )
        # A distinct name lets CockroachDB replace the check in one transaction.
        batch.drop_constraint("ck_scheduled_task_runs_status", type_="check")
        batch.create_check_constraint(
            "ck_scheduled_task_runs_dispatch_status", "status IN (1, 2, 3, 4, 5, 6)"
        )
        batch.create_unique_constraint(
            "uq_scheduled_task_runs_occurrence",
            ["workspace_id", "scheduled_task_id", "trigger_key"],
        )
        batch.create_index(
            "ix_scheduled_task_runs_expired_claims",
            ["status", "lease_expires_at", "workspace_id", "id"],
        )


def downgrade() -> None:
    """Restore the previous schema only after starting runs have been reconciled."""
    runs = sa.table("scheduled_task_runs", sa.column("status"))
    if op.get_bind().execute(sa.select(runs.c.status).where(runs.c.status == 6).limit(1)).first():
        raise RuntimeError("Reconcile starting scheduled-task runs before downgrading")

    with op.batch_alter_table("scheduled_task_runs") as batch:
        batch.drop_index("ix_scheduled_task_runs_expired_claims")
        if op.get_bind().dialect.name == "cockroachdb":
            # CockroachDB removes unique constraints through their backing index.
            op.execute("DROP INDEX scheduled_task_runs@uq_scheduled_task_runs_occurrence CASCADE")
        else:
            batch.drop_constraint("uq_scheduled_task_runs_occurrence", type_="unique")
        batch.drop_constraint("ck_scheduled_task_runs_dispatch_status", type_="check")
        batch.create_check_constraint("ck_scheduled_task_runs_status", "status IN (1, 2, 3, 4, 5)")
        batch.drop_constraint("ck_scheduled_task_runs_trigger_key_size", type_="check")
        batch.drop_column("lease_expires_at")
        batch.drop_column("host_id")
        batch.drop_column("trigger_key")

    with op.batch_alter_table("scheduled_tasks") as batch:
        batch.drop_index("ix_scheduled_tasks_due")
        batch.drop_constraint("ck_scheduled_tasks_delegation_ref_size", type_="check")
        batch.drop_column("delegation_ref")
        batch.drop_column("project_id")
        batch.drop_column("next_run_at")
