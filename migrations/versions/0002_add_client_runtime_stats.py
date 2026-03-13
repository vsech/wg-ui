"""Add cached client runtime stats columns

Revision ID: 0002_add_client_runtime_stats
Revises: 0001_initial_schema
Create Date: 2026-03-13 10:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_client_runtime_stats"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {
        column["name"] for column in inspector.get_columns("clients")
    }

    if "last_handshake" not in existing_columns:
        op.add_column("clients", sa.Column("last_handshake", sa.DateTime(), nullable=True))
    if "bytes_received" not in existing_columns:
        op.add_column("clients", sa.Column("bytes_received", sa.BigInteger(), nullable=True))
    if "bytes_sent" not in existing_columns:
        op.add_column("clients", sa.Column("bytes_sent", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {
        column["name"] for column in inspector.get_columns("clients")
    }

    if "bytes_sent" in existing_columns:
        op.drop_column("clients", "bytes_sent")
    if "bytes_received" in existing_columns:
        op.drop_column("clients", "bytes_received")
    if "last_handshake" in existing_columns:
        op.drop_column("clients", "last_handshake")
