"""RBAC Mappings, Audit and OTP Schema

Revision ID: 0003_links_audit_otp
Revises: 0002_users
Create Date: 2026-03-23 11:07:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '0003_links_audit_otp'
down_revision: Union[str, None] = '0002_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # --- role_module_mapping ---
    op.create_table(
        'role_module_mapping',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('role_uuid', sa.String(36), sa.ForeignKey('role_master.uuid', ondelete='CASCADE'), nullable=False),
        sa.Column('module_uuid', sa.String(36), sa.ForeignKey('module_master.uuid', ondelete='CASCADE'), nullable=False),
        sa.Column('can_read', sa.Boolean(), server_default=sa.false()),
        sa.Column('can_write', sa.Boolean(), server_default=sa.false()),
        sa.Column('can_update', sa.Boolean(), server_default=sa.false()),
        sa.Column('can_delete', sa.Boolean(), server_default=sa.false()),
        sa.Column('can_export', sa.Boolean(), server_default=sa.false()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- access_control_master ---
    op.create_table(
        'access_control_master',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('user_uuid', sa.String(36), sa.ForeignKey('user_login.uuid', ondelete='CASCADE'), nullable=False),
        sa.Column('module_uuid', sa.String(36), sa.ForeignKey('module_master.uuid', ondelete='CASCADE'), nullable=False),
        sa.Column('can_read', sa.Boolean(), server_default=sa.false()),
        sa.Column('can_write', sa.Boolean(), server_default=sa.false()),
        sa.Column('can_update', sa.Boolean(), server_default=sa.false()),
        sa.Column('can_delete', sa.Boolean(), server_default=sa.false()),
        sa.Column('can_export', sa.Boolean(), server_default=sa.false()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- refresh_tokens ---
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('user_uuid', sa.String(36), sa.ForeignKey('user_login.uuid', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(512), unique=True, nullable=False),
        sa.Column('is_revoked', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('expires_at', sa.String(50), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- audit_logs ---
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('user_uuid', sa.String(36), sa.ForeignKey('user_login.uuid', ondelete='SET NULL'), nullable=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('module', sa.String(100), nullable=False),
        sa.Column('method', sa.String(10), nullable=True),
        sa.Column('path', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('response_body', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- otp_verifications ---
    op.create_table(
        'otp_verifications',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('identifier', sa.String(100), nullable=False, index=True),
        sa.Column('otp_type', sa.String(20), nullable=False, default='DEFAULT', index=True),
        sa.Column('otp_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempt_count', sa.Integer(), default=0, nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid'),
        sa.UniqueConstraint('identifier', 'otp_type', name='uq_otp_identifier_type'),
    )

def downgrade() -> None:
    op.drop_table('otp_verifications')
    op.drop_table('audit_logs')
    op.drop_table('refresh_tokens')
    op.drop_table('access_control_master')
    op.drop_table('role_module_mapping')
