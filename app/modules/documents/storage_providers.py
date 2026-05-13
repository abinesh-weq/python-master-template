import os
import uuid
import shutil
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, Tuple
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.secrets import get_secrets


class BaseStorageProvider(ABC):
    """
    Abstract Factory Pattern for Storage Providers.
    All storage implementations must inherit from this base class.
    """

    @abstractmethod
    async def upload(self, file_data: BinaryIO, filename: str, content_type: str) -> Tuple[str, Optional[str]]:
        """
        Upload file and return (file_key, public_url)
        file_key: Internal storage identifier
        public_url: Publicly accessible URL (None for protected files)
        """
        pass

    @abstractmethod
    async def download(self, file_key: str) -> BinaryIO:
        """Download file by storage key"""
        pass

    @abstractmethod
    async def delete(self, file_key: str) -> bool:
        """Delete file by storage key"""
        pass

    @abstractmethod
    async def generate_presigned_url(self, file_key: str, expiration_minutes: int = 15) -> str:
        """Generate temporary access URL for protected files"""
        pass


class LocalStorageProvider(BaseStorageProvider):
    """
    Local filesystem storage provider.
    Saves files to server's filesystem under configured directory.
    """

    def __init__(self, base_path: str = None):
        self.base_path = base_path or getattr(settings, 'LOCAL_STORAGE_PATH', 'data/uploads')
        self.base_url = getattr(settings, 'LOCAL_STORAGE_URL', '/static/uploads')
        self._ensure_directory()

    def _ensure_directory(self):
        """Create upload directory if it doesn't exist"""
        os.makedirs(self.base_path, exist_ok=True)

    def _generate_file_key(self, filename: str) -> str:
        """Generate unique file key with date-based subdirectories"""
        today = datetime.now().strftime('%Y/%m/%d')
        file_uuid = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1]
        return f"{today}/{file_uuid}{ext}"

    def _get_full_path(self, file_key: str) -> str:
        """Get full filesystem path for file key"""
        return os.path.join(self.base_path, file_key)

    async def upload(self, file_data: BinaryIO, filename: str, content_type: str) -> Tuple[str, Optional[str]]:
        """Upload file to local filesystem"""
        file_key = self._generate_file_key(filename)
        full_path = self._get_full_path(file_key)
        
        # Create subdirectories if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write file
        with open(full_path, 'wb') as f:
            shutil.copyfileobj(file_data, f)
        
        # Generate public URL (if accessible)
        public_url = f"{self.base_url}/{file_key}" if self.base_url else None
        
        return file_key, public_url

    async def download(self, file_key: str) -> BinaryIO:
        """Download file from local filesystem"""
        full_path = self._get_full_path(file_key)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file_key}")
        
        return open(full_path, 'rb')

    async def delete(self, file_key: str) -> bool:
        """Delete file from local filesystem"""
        full_path = self._get_full_path(file_key)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False
        except Exception:
            return False

    async def generate_presigned_url(self, file_key: str, expiration_minutes: int = 15) -> str:
        """Generate temporary URL for local files"""
        # For local storage, return the direct URL since it's served by the web server
        return f"{self.base_url}/{file_key}"


class S3StorageProvider(BaseStorageProvider):
    """
    Amazon S3 storage provider using boto3 with AWS credential provider chain.
    Uses centralized secrets management via SSM Parameter Store for configuration.
    
    Authentication Flow:
    1. Local Development: AWS SSO login -> STS provides temporary credentials
    2. Staging/Production: IAM role -> AWS injects temporary credentials
    3. boto3 automatically detects credentials via provider chain
    4. Configuration loaded from centralized secrets manager
    """

    def __init__(self, aws_region: str = None):
        self.secrets_manager = get_secrets()
        self.aws_region = aws_region or self.secrets_manager.get('awsRegion', '')
        
        # Get configuration from centralized secrets manager
        self.bucket_name = self.secrets_manager.get('bucketName')
        if not self.bucket_name:
            raise ValueError("bucketName not found in secrets configuration")
        
        # Additional configuration options
        self.config = {
            'encryption': self.secrets_manager.get('encryption'),
            'publicAccess': self.secrets_manager.get('publicAccess', False),
            'environment': self.secrets_manager.get('environment', 'development')
        }
        
        # Lazy import boto3 to avoid dependency issues
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            self.boto3 = boto3
            self.ClientError = ClientError
            
            # Initialize S3 client with credential provider chain and SSL verification disabled
            # boto3 automatically handles: env vars, AWS CLI login, SSO session, IAM role
            self.s3_client = boto3.client(
                's3',
                region_name=self.aws_region,
                verify=False  # Disable SSL verification for corporate networks
                # No explicit credentials - let boto3 use provider chain
            )
            
        except ImportError:
            raise ImportError("boto3 is required for S3StorageProvider. Install with: pip install boto3")

    def _generate_file_key(self, filename: str) -> str:
        """Generate unique S3 object key"""
        today = datetime.now().strftime('%Y/%m/%d')
        file_uuid = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1]
        return f"uploads/{today}/{file_uuid}{ext}"

    async def upload(self, file_data: BinaryIO, filename: str, content_type: str) -> Tuple[str, Optional[str]]:
        """Upload file to S3"""
        file_key = self._generate_file_key(filename)
        
        try:
            # Reset file pointer
            file_data.seek(0)
            
            # Upload to S3 with enhanced metadata
            upload_args = {
                'ContentType': content_type,
                'Metadata': {
                    'original_filename': filename,
                    'upload_timestamp': datetime.utcnow().isoformat(),
                    'environment': self.config.get('environment', 'development')
                }
            }
            
            # Add server-side encryption if configured
            if self.config.get('encryption'):
                upload_args['ServerSideEncryption'] = self.config['encryption']
            
            self.s3_client.upload_fileobj(
                file_data,
                self.bucket_name,
                file_key,
                ExtraArgs=upload_args
            )
            
            # Generate public URL only if bucket is configured as public
            public_url = None
            if self.config.get('publicAccess', False):
                public_url = f"https://{self.bucket_name}.s3.{self.aws_region}.amazonaws.com/{file_key}"
            
            return file_key, public_url
            
        except self.ClientError as e:
            raise Exception(f"S3 upload failed: {e}")

    async def download(self, file_key: str) -> BinaryIO:
        """Download file from S3"""
        try:
            import io
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            return io.BytesIO(response['Body'].read())
        except self.ClientError as e:
            raise FileNotFoundError(f"S3 file not found: {file_key}")

    async def delete(self, file_key: str) -> bool:
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except self.ClientError:
            return False

    async def generate_presigned_url(self, file_key: str, expiration_minutes: int = 15) -> str:
        """Generate presigned URL for S3 object"""
        try:
            expiration = datetime.utcnow() + timedelta(minutes=expiration_minutes)
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expiration_minutes * 60
            )
        except self.ClientError as e:
            raise Exception(f"Failed to generate presigned URL: {e}")


class GCSStorageProvider(BaseStorageProvider):
    """
    Google Cloud Storage provider using google-cloud-storage.
    Requires GCP credentials and bucket configuration.
    """

    def __init__(self, bucket_name: str = None, project_id: str = None, credentials_path: str = None):
        self.bucket_name = bucket_name or getattr(settings, 'GCS_BUCKET', '')
        self.project_id = project_id or getattr(settings, 'GCP_PROJECT_ID', '')
        self.credentials_path = credentials_path or getattr(settings, 'GCP_CREDENTIALS_PATH', '')
        
        # Lazy import google-cloud-storage to avoid dependency issues
        try:
            from google.cloud import storage
            from google.api_core.exceptions import GoogleAPICallError
            
            self.storage = storage
            self.GoogleAPICallError = GoogleAPICallError
            
            # Initialize GCS client
            if self.credentials_path:
                self.client = storage.Client.from_service_account_json(
                    self.credentials_path, project=self.project_id
                )
            else:
                # Use default credentials (e.g., from environment or metadata server)
                self.client = storage.Client(project=self.project_id)
                
        except ImportError:
            raise ImportError("google-cloud-storage is required for GCSStorageProvider. Install with: pip install google-cloud-storage")

    def _get_bucket(self):
        """Get GCS bucket object"""
        return self.client.bucket(self.bucket_name)

    def _generate_file_key(self, filename: str) -> str:
        """Generate unique GCS object key"""
        today = datetime.now().strftime('%Y/%m/%d')
        file_uuid = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1]
        return f"uploads/{today}/{file_uuid}{ext}"

    async def upload(self, file_data: BinaryIO, filename: str, content_type: str) -> Tuple[str, Optional[str]]:
        """Upload file to GCS"""
        file_key = self._generate_file_key(filename)
        bucket = self._get_bucket()
        
        try:
            # Reset file pointer
            file_data.seek(0)
            
            # Create blob object
            blob = bucket.blob(file_key)
            
            # Upload to GCS with metadata
            blob.upload_from_file(
                file_data,
                content_type=content_type,
                metadata={
                    'original_filename': filename,
                    'upload_timestamp': datetime.utcnow().isoformat()
                }
            )
            
            # Generate public URL (if bucket is public)
            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{file_key}"
            
            return file_key, public_url
            
        except self.GoogleAPICallError as e:
            raise Exception(f"GCS upload failed: {e}")

    async def download(self, file_key: str) -> BinaryIO:
        """Download file from GCS"""
        try:
            import io
            bucket = self._get_bucket()
            blob = bucket.blob(file_key)
            
            # Download file content
            content = blob.download_as_bytes()
            return io.BytesIO(content)
            
        except self.GoogleAPICallError as e:
            raise FileNotFoundError(f"GCS file not found: {file_key}")

    async def delete(self, file_key: str) -> bool:
        """Delete file from GCS"""
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(file_key)
            blob.delete()
            return True
        except self.GoogleAPICallError:
            return False

    async def generate_presigned_url(self, file_key: str, expiration_minutes: int = 15) -> str:
        """Generate signed URL for GCS object"""
        try:
            from datetime import timedelta
            
            bucket = self._get_bucket()
            blob = bucket.blob(file_key)
            
            # Generate signed URL
            expiration = datetime.utcnow() + timedelta(minutes=expiration_minutes)
            url = blob.generate_signed_url(
                expiration=expiration,
                method='GET',
                version='v4'
            )
            
            return url
            
        except self.GoogleAPICallError as e:
            raise Exception(f"Failed to generate signed URL: {e}")


def get_storage_provider(provider_type: str) -> BaseStorageProvider:
    """
    Factory function to get appropriate storage provider.
    
    For S3 provider, uses modern AWS authentication flow:
    - Local: AWS SSO login -> STS temporary credentials
    - Production: IAM role -> AWS injected credentials
    - Configuration from SSM Parameter Store
    """
    if provider_type.upper() == "LOCAL":
        return LocalStorageProvider()
    elif provider_type.upper() == "S3":
        return S3StorageProvider()
    elif provider_type.upper() == "GCS":
        return GCSStorageProvider()
    else:
        raise ValueError(f"Unsupported storage provider: {provider_type}")
