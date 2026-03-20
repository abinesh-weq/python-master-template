"""Initial schema + seed data: all tables, ROLE_ADMIN, ROLE_USER, and default modules

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-19 16:41:00

"""
from typing import Sequence, Union
import uuid
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def now():
    return datetime.utcnow()


def gen_uuid():
    return str(uuid.uuid4())


def upgrade() -> None:
    # ── user_login ────────────────────────────────────────────────────────────
    op.create_table(
        "user_login",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), unique=True, nullable=False),
        sa.Column("phone_number", sa.String(20), unique=True, nullable=True),
        sa.Column("password", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False, server_default="LOCAL"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_biometric_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("role_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── role_master ───────────────────────────────────────────────────────────
    op.create_table(
        "role_master",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("pwd_login_allowed", sa.Boolean(), server_default=sa.true()),
        sa.Column("mobile_otp_login_allowed", sa.Boolean(), server_default=sa.true()),
        sa.Column("email_otp_login_allowed", sa.Boolean(), server_default=sa.true()),
        sa.Column("social_login_allowed", sa.Boolean(), server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── module_master ─────────────────────────────────────────────────────────
    op.create_table(
        "module_master",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module_code", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── role_module_mapping ───────────────────────────────────────────────────
    op.create_table(
        "role_module_mapping",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("role_master.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_id", sa.String(36), sa.ForeignKey("module_master.id", ondelete="CASCADE"), nullable=False),
        sa.Column("can_read", sa.Boolean(), server_default=sa.false()),
        sa.Column("can_write", sa.Boolean(), server_default=sa.false()),
        sa.Column("can_update", sa.Boolean(), server_default=sa.false()),
        sa.Column("can_delete", sa.Boolean(), server_default=sa.false()),
        sa.Column("can_export", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── access_control_master ─────────────────────────────────────────────────
    op.create_table(
        "access_control_master",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("user_login.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_id", sa.String(36), sa.ForeignKey("module_master.id", ondelete="CASCADE"), nullable=False),
        sa.Column("can_read", sa.Boolean(), server_default=sa.false()),
        sa.Column("can_write", sa.Boolean(), server_default=sa.false()),
        sa.Column("can_update", sa.Boolean(), server_default=sa.false()),
        sa.Column("can_delete", sa.Boolean(), server_default=sa.false()),
        sa.Column("can_export", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── refresh_tokens ────────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("user_login.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(512), unique=True, nullable=False),
        sa.Column("is_revoked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("expires_at", sa.String(50), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── predefined_master ─────────────────────────────────────────────────────
    op.create_table(
        "predefined_master",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(100), nullable=False, index=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("predefined_master.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── communication_provider_config ─────────────────────────────────────────
    op.create_table(
        "communication_provider_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── provider_api_metadata ─────────────────────────────────────────────────
    op.create_table(
        "provider_api_metadata",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("communication_provider_config.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("api_key", sa.String(500), nullable=True),
        sa.Column("api_secret", sa.String(500), nullable=True),
        sa.Column("headers_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── provider_api_mapping ──────────────────────────────────────────────────
    op.create_table(
        "provider_api_mapping",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("communication_provider_config.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_code", sa.String(100), nullable=False),
        sa.Column("endpoint_path", sa.String(500), nullable=False),
        sa.Column("http_method", sa.String(10), server_default="POST"),
        sa.Column("request_body_template", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── notification_template_master ──────────────────────────────────────────
    op.create_table(
        "notification_template_master",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(100), unique=True, nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── notification_log ──────────────────────────────────────────────────────
    op.create_table(
        "notification_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recipient", sa.String(200), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("template_code", sa.String(100), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=True),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ── notification_payload_log ──────────────────────────────────────────────
    op.create_table(
        "notification_payload_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("notification_log_id", sa.String(36), sa.ForeignKey("notification_log.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_payload", sa.Text(), nullable=True),
        sa.Column("response_payload", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # ════════════════════════════════════════════════════════════════════════════
    # SEED DATA
    # ════════════════════════════════════════════════════════════════════════════
    seed_ts = now()

    # ── Roles ─────────────────────────────────────────────────────────────────
    role_admin_id = gen_uuid()
    role_user_id = gen_uuid()

    op.bulk_insert(
        sa.table(
            "role_master",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("pwd_login_allowed", sa.Boolean),
            sa.column("mobile_otp_login_allowed", sa.Boolean),
            sa.column("email_otp_login_allowed", sa.Boolean),
            sa.column("social_login_allowed", sa.Boolean),
            sa.column("is_active", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "id": role_admin_id,
                "name": "ROLE_ADMIN",
                "pwd_login_allowed": True,
                "mobile_otp_login_allowed": True,
                "email_otp_login_allowed": True,
                "social_login_allowed": False,
                "is_active": True,
                "created_at": seed_ts,
                "updated_at": seed_ts,
            },
            {
                "id": role_user_id,
                "name": "ROLE_USER",
                "pwd_login_allowed": True,
                "mobile_otp_login_allowed": True,
                "email_otp_login_allowed": True,
                "social_login_allowed": True,
                "is_active": True,
                "created_at": seed_ts,
                "updated_at": seed_ts,
            },
        ],
    )

    # ── Modules ───────────────────────────────────────────────────────────────
    modules = [
        ("USER_MANAGEMENT", "User Management"),
        ("RBAC_MANAGEMENT", "RBAC Management"),
        ("MASTER", "Master Data"),
        ("INVENTORY", "Inventory"),
        ("REPORTING", "Reporting"),
        ("DASHBOARD", "Dashboard"),
    ]
    module_rows = []
    module_ids = {}
    for code, display_name in modules:
        mid = gen_uuid()
        module_ids[code] = mid
        module_rows.append(
            {
                "id": mid,
                "module_code": code,
                "display_name": display_name,
                "is_active": True,
                "created_at": seed_ts,
                "updated_at": seed_ts,
            }
        )

    op.bulk_insert(
        sa.table(
            "module_master",
            sa.column("id", sa.String),
            sa.column("module_code", sa.String),
            sa.column("display_name", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        module_rows,
    )

    # ── Role-Module Mappings: ROLE_ADMIN gets full access to everything ────────
    admin_mappings = []
    for code, _ in modules:
        admin_mappings.append(
            {
                "id": gen_uuid(),
                "role_id": role_admin_id,
                "module_id": module_ids[code],
                "can_read": True,
                "can_write": True,
                "can_update": True,
                "can_delete": True,
                "can_export": True,
                "created_at": seed_ts,
                "updated_at": seed_ts,
            }
        )

    # ── Role-Module Mappings: ROLE_USER gets read-only on DASHBOARD + MASTER ──
    user_mappings = []
    for code in ["DASHBOARD", "MASTER"]:
        user_mappings.append(
            {
                "id": gen_uuid(),
                "role_id": role_user_id,
                "module_id": module_ids[code],
                "can_read": True,
                "can_write": False,
                "can_update": False,
                "can_delete": False,
                "can_export": False,
                "created_at": seed_ts,
                "updated_at": seed_ts,
            }
        )

    all_mappings = admin_mappings + user_mappings
    op.bulk_insert(
        sa.table(
            "role_module_mapping",
            sa.column("id", sa.String),
            sa.column("role_id", sa.String),
            sa.column("module_id", sa.String),
            sa.column("can_read", sa.Boolean),
            sa.column("can_write", sa.Boolean),
            sa.column("can_update", sa.Boolean),
            sa.column("can_delete", sa.Boolean),
            sa.column("can_export", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        all_mappings,
    )

    # ── Notification Templates ─────────────────────────────────────────────────
    op.bulk_insert(
        sa.table(
            "notification_template_master",
            sa.column("id", sa.String),
            sa.column("code", sa.String),
            sa.column("subject", sa.String),
            sa.column("body_template", sa.Text),
            sa.column("channel", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "id": gen_uuid(),
                "code": "OTP_EMAIL",
                "subject": "Your OTP Code",
                "body_template": "<h1>Your OTP</h1><p>Hello {{USERNAME}}, your one-time code is <strong>{{OTP}}</strong>. It expires in 5 minutes.</p>",
                "channel": "EMAIL",
                "is_active": True,
                "created_at": seed_ts,
                "updated_at": seed_ts,
            },
            {
                "id": gen_uuid(),
                "code": "OTP_SMS",
                "subject": None,
                "body_template": "Your OTP is {{OTP}}. Valid for 5 minutes. Do not share it with anyone.",
                "channel": "SMS",
                "is_active": True,
                "created_at": seed_ts,
                "updated_at": seed_ts,
            },
            {
                "id": gen_uuid(),
                "code": "PASSWORD_RESET_EMAIL",
                "subject": "Password Reset Request",
                "body_template": "<h1>Password Reset</h1><p>Hello {{USERNAME}}, use OTP <strong>{{OTP}}</strong> to reset your password. Valid for 5 minutes.</p>",
                "channel": "EMAIL",
                "is_active": True,
                "created_at": seed_ts,
                "updated_at": seed_ts,
            },
        ],
    )


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_table("notification_payload_log")
    op.drop_table("notification_log")
    op.drop_table("notification_template_master")
    op.drop_table("provider_api_mapping")
    op.drop_table("provider_api_metadata")
    op.drop_table("communication_provider_config")
    op.drop_table("predefined_master")
    op.drop_table("refresh_tokens")
    op.drop_table("access_control_master")
    op.drop_table("role_module_mapping")
    op.drop_table("module_master")
    op.drop_table("role_master")
    op.drop_table("user_login")
