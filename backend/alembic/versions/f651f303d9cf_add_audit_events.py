"""add_audit_events

Revision ID: f651f303d9cf
Revises: 476cc0dad2d2
Create Date: 2026-10-03 00:56:42.878566

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f651f303d9cf"
down_revision: str | Sequence[str] | None = "476cc0dad2d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "series_id",
            sa.String(length=36),
            sa.ForeignKey("series.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "episode_id",
            sa.String(length=36),
            sa.ForeignKey("episodes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "scene_id",
            sa.String(length=36),
            sa.ForeignKey("scenes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "shot_id",
            sa.String(length=36),
            sa.ForeignKey("shots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "asset_id",
            sa.String(length=36),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("job_id", sa.String(length=50), nullable=True),
        sa.Column("production_run_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_series_id", "audit_events", ["series_id"])
    op.create_index("ix_audit_events_episode_id", "audit_events", ["episode_id"])
    op.create_index("ix_audit_events_job_id", "audit_events", ["job_id"])
    op.create_index("ix_audit_events_production_run_id", "audit_events", ["production_run_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_audit_events_production_run_id", table_name="audit_events")
    op.drop_index("ix_audit_events_job_id", table_name="audit_events")
    op.drop_index("ix_audit_events_episode_id", table_name="audit_events")
    op.drop_index("ix_audit_events_series_id", table_name="audit_events")
    op.drop_table("audit_events")
