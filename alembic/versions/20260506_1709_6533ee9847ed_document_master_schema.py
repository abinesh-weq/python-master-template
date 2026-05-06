"""document master schema

Revision ID: 6533ee9847ed
Revises: ed034d228722
Create Date: 2026-05-06 17:09:23.543532

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6533ee9847ed'
down_revision: Union[str, None] = 'ed034d228722'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- document_master ---
    op.create_table(
        'document_master',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('uuid', sa.String(36), unique=True, index=True, nullable=False),
        sa.Column('original_name', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('provider_type', sa.Enum('LOCAL', 'S3', 'GCS', name='storageprovider'), nullable=False, default='LOCAL'),
        sa.Column('access_level', sa.Enum('OPEN', 'PROTECTED', name='accesslevel'), nullable=False, default='PROTECTED'),
        sa.Column('file_key', sa.String(500), nullable=False),
        sa.Column('file_url', sa.String(1000), nullable=True),
        sa.Column('uploaded_by', sa.String(36), sa.ForeignKey('user_login.uuid', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('description', sa.String(1000), nullable=True),
        sa.Column('tags', sa.String(500), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('uuid')
    )
    
    # Create indexes for better performance
    op.create_index('idx_document_master_uploaded_by', 'document_master', ['uploaded_by'])
    op.create_index('idx_document_master_provider_type', 'document_master', ['provider_type'])
    op.create_index('idx_document_master_access_level', 'document_master', ['access_level'])
    op.create_index('idx_document_master_is_active', 'document_master', ['is_active'])
    op.create_index('idx_document_master_is_deleted', 'document_master', ['is_deleted'])
    op.create_index('idx_document_master_uploaded_at', 'document_master', ['uploaded_at'])

def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_document_master_uploaded_at', table_name='document_master')
    op.drop_index('idx_document_master_is_deleted', table_name='document_master')
    op.drop_index('idx_document_master_is_active', table_name='document_master')
    op.drop_index('idx_document_master_access_level', table_name='document_master')
    op.drop_index('idx_document_master_provider_type', table_name='document_master')
    op.drop_index('idx_document_master_uploaded_by', table_name='document_master')
    
    # Drop the table
    op.drop_table('document_master')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS storageprovider')
    op.execute('DROP TYPE IF EXISTS accesslevel')
