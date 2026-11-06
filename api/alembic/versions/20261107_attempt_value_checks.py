"""attempt value checks

Their values settled once tickets 07 to 10 wrote them, so the columns can now be held to them.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

POD_STATUSES = (
    "'awaiting_pod', 'checking', 'retake_requested', 'needs_review', "
    "'verified', 'disputed', 'invoiced'"
)


def upgrade() -> None:
    op.create_check_constraint(
        op.f("ck_pod_attempts_ai_status"),
        "pod_attempts",
        "ai_status IN ('pending', 'done', 'failed', 'skipped')",
    )
    op.create_check_constraint(
        op.f("ck_pod_attempts_device_check"),
        "pod_attempts",
        "device_check IN ('passed', 'sent_anyway')",
    )
    op.create_check_constraint(
        op.f("ck_pod_attempts_outcome"), "pod_attempts", f"outcome IN ({POD_STATUSES})"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_pod_attempts_outcome"), "pod_attempts", type_="check")
    op.drop_constraint(op.f("ck_pod_attempts_device_check"), "pod_attempts", type_="check")
    op.drop_constraint(op.f("ck_pod_attempts_ai_status"), "pod_attempts", type_="check")
