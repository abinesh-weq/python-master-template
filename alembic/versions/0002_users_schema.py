"""UserLogin Schema

Revision ID: 0002_users
Revises: 0001_rbac
Create Date: 2026-03-23 11:06:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '0002_users'
down_revision: Union[str, None] = '0001_rbac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # --- user_login ---
    op.create_table(
        'user_login',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('role_uuid', sa.String(36), sa.ForeignKey('role_master.uuid', ondelete='SET NULL'), nullable=True),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('email', sa.String(100), unique=True, nullable=False),
        sa.Column('phone_number', sa.String(20), unique=True, nullable=True),
        sa.Column('password', sa.String(255), nullable=True),
        sa.Column('provider', sa.String(20), nullable=False, server_default='LOCAL'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_mfa_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_biometric_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('device_id', sa.String(255), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

def downgrade() -> None:
    op.drop_table('user_login')
