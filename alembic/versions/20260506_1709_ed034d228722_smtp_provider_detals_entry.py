"""smtp provider detals entry

Revision ID: ed034d228722
Revises: c1ae134529ba
Create Date: 2026-05-06 17:09:06.259607

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import uuid

# revision identifiers, used by Alembic.
revision: str = 'ed034d228722'
down_revision: Union[str, None] = 'c1ae134529ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Generate UUIDs
    provider_uuid = str(uuid.uuid4())
    metadata_uuid = str(uuid.uuid4())
    mapping_uuid = str(uuid.uuid4())
    otp_template_uuid = str(uuid.uuid4())
    reset_template_uuid = str(uuid.uuid4())

    # Insert Gmail SMTP provider configuration
    op.execute(f"""
        INSERT INTO communication_provider_config (
            uuid, 
            provider_name, 
            provider_type, 
            priority, 
            is_active,
            created_at,
            updated_at
        ) VALUES (
            '{provider_uuid}',
            'GMAIL_SMTP',
            'EMAIL',
            1,
            TRUE,
            NOW(),
            NOW()
        );
    """)

    # Insert provider API metadata with SMTP configuration
    op.execute(f"""
        INSERT INTO provider_api_metadata (
            uuid,
            provider_uuid,
            base_url,
            api_key,
            api_secret,
            headers_json,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            '{metadata_uuid}',
            '{provider_uuid}',
            'smtp.gmail.com:587',
            'abineshatweq@gmail.com',
            'zhqeyvoyjbkxmdlm',
            '{{"from_address": "noreply@audi.com"}}',
            TRUE,
            NOW(),
            NOW()
        );
    """)

    # Insert provider API mapping for OTP_EMAIL action
    op.execute(f"""
        INSERT INTO provider_api_mapping (
            uuid,
            provider_uuid,
            action_code,
            endpoint_path,
            http_method,
            request_body_template,
            created_at,
            updated_at
        ) VALUES (
            '{mapping_uuid}',
            '{provider_uuid}',
            'OTP_EMAIL',
            '',
            'POST',
            '{{"recipient": "{{RECIPIENT}}", "subject": "{{SUBJECT}}", "body": "{{BODY}}"}}',
            NOW(),
            NOW()
        );
    """)

    # Insert notification template for Password Reset Email
    op.execute(f"""
        INSERT INTO notification_template_master (
            uuid,
            code,
            subject,
            body_template,
            channel,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            '{reset_template_uuid}',
            'PASSWORD_RESET_EMAIL',
            'Password Reset OTP',
            'Hi {{{{USERNAME}}}},

Your password reset OTP code is: {{{{OTP}}}}

This code will expire in 5 minutes.

Best,
WeQ Team',
            'EMAIL',
            TRUE,
            NOW(),
            NOW()
        );
    """)

def downgrade() -> None:
    # Remove the inserted data in reverse order using template codes
    op.execute("DELETE FROM notification_template_master WHERE code IN ('OTP_EMAIL', 'PASSWORD_RESET_EMAIL');")
    op.execute("DELETE FROM provider_api_mapping WHERE action_code = 'OTP_EMAIL';")
    op.execute("DELETE FROM provider_api_metadata WHERE base_url = 'smtp.gmail.com:587';")
    op.execute("DELETE FROM communication_provider_config WHERE provider_name = 'GMAIL_SMTP';")

