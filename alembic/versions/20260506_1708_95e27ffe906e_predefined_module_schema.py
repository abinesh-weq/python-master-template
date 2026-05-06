"""predefined module schema

Revision ID: 95e27ffe906e
Revises: 8147742a2f5b
Create Date: 2026-05-06 17:08:20.414050

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95e27ffe906e'
down_revision: Union[str, None] = '8147742a2f5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- communication_provider_config ---
    op.create_table(
        'communication_provider_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('provider_name', sa.String(100), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- provider_api_metadata ---
    op.create_table(
        'provider_api_metadata',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('provider_uuid', sa.String(36), sa.ForeignKey('communication_provider_config.uuid', ondelete='CASCADE'), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('api_key', sa.String(500), nullable=True),
        sa.Column('api_secret', sa.String(500), nullable=True),
        sa.Column('headers_json', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- provider_api_mapping ---
    op.create_table(
        'provider_api_mapping',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('provider_uuid', sa.String(36), sa.ForeignKey('communication_provider_config.uuid', ondelete='CASCADE'), nullable=False),
        sa.Column('action_code', sa.String(100), nullable=False),
        sa.Column('endpoint_path', sa.String(500), nullable=False),
        sa.Column('http_method', sa.String(10), server_default='POST'),
        sa.Column('request_body_template', sa.Text(), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- notification_template_master ---
    op.create_table(
        'notification_template_master',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('code', sa.String(100), unique=True, nullable=False),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('body_template', sa.Text(), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- notification_log ---
    op.create_table(
        'notification_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('recipient', sa.String(200), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('template_code', sa.String(100), nullable=False),
        sa.Column('provider_name', sa.String(100), nullable=True),
        sa.Column('http_status_code', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- notification_payload_log ---
    op.create_table(
        'notification_payload_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('notification_log_uuid', sa.String(36), sa.ForeignKey('notification_log.uuid', ondelete='CASCADE'), nullable=False),
        sa.Column('request_payload', sa.Text(), nullable=True),
        sa.Column('response_payload', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- predefined_master ---
    op.create_table(
        'predefined_master',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False, index=True),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_uuid', sa.String(36), sa.ForeignKey('predefined_master.uuid', ondelete='RESTRICT'), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

def downgrade() -> None:
    op.drop_table('predefined_master')
    op.drop_table('notification_payload_log')
    op.drop_table('notification_log')
    op.drop_table('notification_template_master')
    op.drop_table('provider_api_mapping')
    op.drop_table('provider_api_metadata')
    op.drop_table('communication_provider_config')
