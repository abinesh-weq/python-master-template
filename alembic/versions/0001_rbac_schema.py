"""Initial RBAC Schema: RoleMaster, ModuleMaster

Revision ID: 0001_rbac
Revises: 
Create Date: 2026-03-23 11:05:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '0001_rbac'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # --- role_master ---
    op.create_table(
        'role_master',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('pwd_login_allowed', sa.Boolean(), server_default=sa.true()),
        sa.Column('mobile_otp_login_allowed', sa.Boolean(), server_default=sa.true()),
        sa.Column('email_otp_login_allowed', sa.Boolean(), server_default=sa.true()),
        sa.Column('social_login_allowed', sa.Boolean(), server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

    # --- module_master ---
    op.create_table(
        'module_master',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('module_code', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true()),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )

def downgrade() -> None:
    op.drop_table('module_master')
    op.drop_table('role_master')
