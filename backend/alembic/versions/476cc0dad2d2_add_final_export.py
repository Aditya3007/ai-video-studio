"""add_final_export

Revision ID: 476cc0dad2d2
Revises: 2b320a989326
Create Date: 2026-10-02 23:42:38.050372

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "476cc0dad2d2"
down_revision: str | Sequence[str] | None = "2b320a989326"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "video_assemblies",
        sa.Column("final_asset_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "video_assemblies",
        sa.Column("rendered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_video_assemblies_final_asset_id"),
        "video_assemblies",
        ["final_asset_id"],
        unique=False,
    )
    with op.batch_alter_table("video_assemblies") as batch_op:
        batch_op.create_foreign_key(
            "fk_video_assemblies_final_asset_id_assets",
            "assets",
            ["final_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("video_assemblies") as batch_op:
        batch_op.drop_constraint("fk_video_assemblies_final_asset_id_assets", type_="foreignkey")
    op.drop_index(op.f("ix_video_assemblies_final_asset_id"), table_name="video_assemblies")
    op.drop_column("video_assemblies", "rendered_at")
    op.drop_column("video_assemblies", "final_asset_id")
