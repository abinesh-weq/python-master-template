import os
import json
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load .env file to ensure environment variables are available
load_dotenv()

from app.core.config import settings



class SecretsManager:
    """
    Centralized secrets management using AWS SSM Parameter Store.
    
    This class replicates the Java approach where all secrets are stored
    as a single JSON blob in an encrypted SSM parameter and loaded at startup.
    
    Usage:
        secrets = SecretsManager()
        db_url = secrets.get("url")
        bucket_name = secrets.get("bucketName")
    """
    
    def __init__(self):
        self._secrets: Dict[str, Any] = {}
        self._loaded = False
        self._load_secrets()
    
    def _should_load_from_ssm(self) -> bool:
        """Check if we should load secrets from SSM based on parameter name"""
        param_name = os.getenv("SSM_PARAM_NAME", "")
        should_load = bool(param_name)
        return should_load  # Load from SSM if parameter name is provided
    
    def _load_secrets(self):
        """Load secrets from SSM Parameter Store or environment variables"""
        if self._loaded:
            return
        
        if not self._should_load_from_ssm():
            # For development without SSM parameter, use environment variables or .env file
            self._load_from_environment()
            self._loaded = True
            return
        
        try:
            
            # Get SSM parameter name from environment or use default
            param_name = os.getenv(
                "SSM_PARAM_NAME", 
                getattr(settings, 'SSM_PARAM_NAME', '')
            )
            
            # Get AWS region from environment or settings
            aws_region = os.getenv(
                "AWS_REGION",
                getattr(settings, 'AWS_REGION', 'ap-south-1')
            )
            
            # Create SSM client with SSL verification disabled
            ssm_client = boto3.client(
                'ssm', 
                region_name=aws_region,
                verify=False
            )
            
            # Fetch parameter with decryption
            response = ssm_client.get_parameter(
                Name=param_name,
                WithDecryption=True
            )
            
            # Parse JSON
            self._secrets = json.loads(response['Parameter']['Value'])
            
            # Inject all secrets into environment variables for downstream use
            self._inject_into_environment()
            
            self._loaded = True
            
        except ClientError as e:
            raise RuntimeError(f"AWS SSM Access Failure: {e}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in SSM parameter: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load secrets: {e}")
    
    def _load_from_environment(self):
        """Load secrets from environment variables for development"""
        
        # Map common environment variable names to the expected keys
        env_mappings = {
            'DATABASE_URL': 'url',
            'DATABASE_USER': 'username', 
            'DATABASE_PASSWORD': 'password',
            'S3_BUCKET_NAME': 'bucketName',
            'JWT_SECRET': 'secretKey',
            'GOOGLE_API_KEY': 'googleKey',
            'OAUTH_CLIENT_ID': 'clientId',
            'OAUTH_CLIENT_SECRET': 'clientSecret',
            'GOOGLE_CLIENT_CUSTOMER_ID': 'clientCustomerId',
            'GOOGLE_CLIENT_CUSTOMER_SECRET': 'clientCustomerSecret',
            'KYC_REQUEST_USERNAME': 'kycRequestUsername',
            'KYC_REQUEST_PASSWORD': 'kycRequestPassword',
            'FACEBOOK_CLIENT_SECRET': 'facebookClientSecret',
            'CLIENT_ANDROID_ID': 'clientAndroidId',
            'CLIENT_IOS_ID': 'clientIosId',
            'HOST_ANDROID_ID': 'hostAndroidId',
            'HOST_IOS_ID': 'hostIosId',
            'OTP_KEY': 'otpKey'
        }
        
        for env_key, secret_key in env_mappings.items():
            value = os.getenv(env_key)
            if value:
                self._secrets[secret_key] = value
    
    def _inject_into_environment(self):
        """Inject secrets into environment variables for downstream consumption"""
        for key, value in self._secrets.items():
            if isinstance(value, str):
                # Use uppercase keys for environment variables
                env_key = key.upper()
                os.environ[env_key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a secret value by key"""
        if not self._loaded:
            self._load_secrets()
        return self._secrets.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all secrets as a dictionary"""
        if not self._loaded:
            self._load_secrets()
        return self._secrets.copy()
    
    def reload(self):
        """Force reload secrets from SSM"""
        self._loaded = False
        self._secrets.clear()
        self._load_secrets()


# Global instance for application-wide use
secrets_manager = SecretsManager()


def get_secrets() -> SecretsManager:
    """Get the global secrets manager instance"""
    return secrets_manager


# Convenience functions for common use cases
def get_database_config() -> Dict[str, str]:
    """Get database configuration"""
    return {
        'url': secrets_manager.get('url'),
        'username': secrets_manager.get('username'),
        'password': secrets_manager.get('password')
    }


def get_s3_config() -> Dict[str, str]:
    """Get S3 configuration"""
    return {
        'bucket_name': secrets_manager.get('bucketName'),
        'region': secrets_manager.get('awsRegion', '')
    }


def get_jwt_config() -> Dict[str, str]:
    """Get JWT configuration"""
    return {
        'secret_key': secrets_manager.get('secretKey'),
        'algorithm': 'HS256'
    }


def get_oauth_config() -> Dict[str, str]:
    """Get OAuth configuration"""
    return {
        'client_id': secrets_manager.get('clientId'),
        'client_secret': secrets_manager.get('clientSecret'),
        'google_key': secrets_manager.get('googleKey')
    }


if __name__ == "__main__":
    """Test the secrets manager when run directly"""
    try:
        secrets = get_secrets()
    except Exception:
        pass
