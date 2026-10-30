"""Create users table.

Revision ID: 20261029_01
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import Uuid

revision = "20261029_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "email = lower(trim(email))",
            name="ck_users_email_normalized",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )


def downgrade() -> None:
    raise RuntimeError("The initial users migration is intentionally irreversible.")
