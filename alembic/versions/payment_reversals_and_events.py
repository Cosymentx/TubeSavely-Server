"""payment reversal metadata and provider event audit

Revision ID: payment_reversals_and_events
Revises: remove_email_unique_constraint
"""
from alembic import op
import sqlalchemy as sa

revision = "payment_reversals_and_events"
down_revision = "remove_email_unique_constraint"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # Older installations were created with SQLAlchemy create_all and have no
    # complete Alembic baseline. Bootstrap only missing tables for fresh DBs.
    from app.db.base import Base
    Base.metadata.create_all(bind=bind)

    inspector = sa.inspect(bind)
    payment_columns = {item["name"] for item in inspector.get_columns("payments")}

    additions = (
        ("credit_reversal_applied", sa.Boolean(), sa.false()),
        ("reversal_reason", sa.String(length=100), None),
        ("refunded_at", sa.DateTime(timezone=True), None),
        ("disputed_at", sa.DateTime(timezone=True), None),
    )
    for name, column_type, server_default in additions:
        if name not in payment_columns:
            op.add_column(
                "payments",
                sa.Column(
                    name,
                    column_type,
                    nullable=False if name == "credit_reversal_applied" else True,
                    server_default=server_default,
                ),
            )

    inspector = sa.inspect(bind)
    if "payment_events" not in inspector.get_table_names():
        op.create_table(
            "payment_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=True),
            sa.Column("provider", sa.String(length=30), nullable=False),
            sa.Column("provider_event_id", sa.String(length=255), nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("payload_sha256", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("provider_event_id", name="uq_payment_events_provider_event_id"),
        )
        op.create_index("ix_payment_events_payment_id", "payment_events", ["payment_id"])
        op.create_index("ix_payment_events_provider", "payment_events", ["provider"])
        op.create_index("ix_payment_events_provider_event_id", "payment_events", ["provider_event_id"], unique=True)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "payment_events" in inspector.get_table_names():
        op.drop_table("payment_events")

    if "payments" in inspector.get_table_names():
        columns = {item["name"] for item in inspector.get_columns("payments")}
        for name in ("disputed_at", "refunded_at", "reversal_reason", "credit_reversal_applied"):
            if name in columns:
                op.drop_column("payments", name)
