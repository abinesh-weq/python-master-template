"""Seed Data: Roles, Modules, Admin Users, Templates

Revision ID: 0005_seed
Revises: 0004_integration_predefined
Create Date: 2026-03-23 11:10:00

"""

from typing import Sequence, Union
import uuid
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0005_seed"
down_revision: Union[str, None] = "0004_integration_predefined"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def gen_uuid():
    return str(uuid.uuid4())


def upgrade() -> None:
    # --- Seed Roles ---
    role_admin_uuid = gen_uuid()
    role_user_uuid = gen_uuid()

    op.execute(
        f"INSERT INTO role_master (uuid, name, is_active) VALUES ('{role_admin_uuid}', 'admin', 1)"
    )
    op.execute(
        f"INSERT INTO role_master (uuid, name, is_active) VALUES ('{role_user_uuid}', 'user', 1)"
    )

    # --- Seed Modules ---
    modules = [
        ("USER_MANAGEMENT", "User Management"),
        ("RBAC_MANAGEMENT", "RBAC Management"),
        ("INTEGRATION_MANAGEMENT", "Integration Management"),
        ("MASTER", "Master Data"),
        ("INVENTORY", "Inventory"),
        ("REPORTING", "Reporting"),
        ("DASHBOARD", "Dashboard"),
    ]

    module_uuids = {}
    for code, name in modules:
        u = gen_uuid()
        module_uuids[code] = u
        op.execute(
            f"INSERT INTO module_master (uuid, module_code, display_name, is_active) VALUES ('{u}', '{code}', '{name}', 1)"
        )

    # --- Role-Module Mappings ---
    # Give ADMIN full access to all modules
    # We need to get the IDs. Since it's a fresh DB, ADMIN is likely ID 1.
    # But it's safer to use subqueries or just trust the sequence if we just cleared the DB.

    for code, _ in modules:
        op.execute(
            f"""
            INSERT INTO role_module_mapping (uuid, role_uuid, module_uuid, can_read, can_write, can_update, can_delete, can_export)
            SELECT '{gen_uuid()}', r.uuid, m.uuid, 1, 1, 1, 1, 1
            FROM role_master r, module_master m
            WHERE r.name = 'admin' AND m.module_code = '{code}'
        """
        )

    # Give USER read-only access to DASHBOARD and MASTER
    for code in ["DASHBOARD", "MASTER"]:
        op.execute(
            f"""
            INSERT INTO role_module_mapping (uuid, role_uuid, module_uuid, can_read, can_write, can_update, can_delete, can_export)
            SELECT '{gen_uuid()}', r.uuid, m.uuid, 1, 0, 0, 0, 0
            FROM role_master r, module_master m
            WHERE r.name = 'user' AND m.module_code = '{code}'
        """
        )

    # --- Notification Templates ---
    op.execute(
        f"""
        INSERT INTO notification_template_master (uuid, code, subject, body_template, channel, is_active)
        VALUES ('{gen_uuid()}', 'OTP_EMAIL', 'Your OTP Code', '<h1>Your OTP</h1><p>Hello {{USERNAME}}, your one-time code is <strong>{{OTP}}</strong>. It expires in 5 minutes.</p>', 'EMAIL', 1)
    """
    )
    op.execute(
        f"""
        INSERT INTO notification_template_master (uuid, code, subject, body_template, channel, is_active)
        VALUES ('{gen_uuid()}', 'OTP_SMS', NULL, 'Your OTP is {{OTP}}. Valid for 5 minutes. Do not share it with anyone.', 'SMS', 1)
    """
    )


def downgrade() -> None:
    op.execute("DELETE FROM notification_template_master")
    op.execute("DELETE FROM user_login")
    op.execute("DELETE FROM role_module_mapping")
    op.execute("DELETE FROM module_master")
    op.execute("DELETE FROM role_master")
