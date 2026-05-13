import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional

import httpx


class EmailService:
    """SDK wrapper for email operations using SMTP"""
    
    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
    
    async def send_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        """Send email using SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            if html_body:
                msg.attach(MIMEText(body, 'plain'))
                msg.attach(MIMEText(html_body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            return False


class SMSService:
    """SDK wrapper for SMS operations (placeholder for Twilio integration)"""
    
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
    
    async def send_sms(self, to_number: str, message: str) -> bool:
        """Send SMS using Twilio (placeholder implementation)"""
        try:
            # This would require twilio library: pip install twilio
            # from twilio.rest import Client
            # client = Client(self.account_sid, self.auth_token)
            # message = client.messages.create(
            #     body=message,
            #     from_=self.from_number,
            #     to=to_number
            # )
            # return True
            
            return True
        except Exception as e:
            return False


class HTTPRequestService:
    """SDK wrapper for HTTP requests"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def post_json(self, url: str, headers: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Dict:
        """Make POST request with JSON data"""
        try:
            response = await self.client.post(
                url=url,
                headers=headers or {},
                json=json_data
            )
            response.raise_for_status()
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "data": response.json() if response.content else {}
            }
        except httpx.HTTPStatusError as e:
            return {
                "status_code": e.response.status_code,
                "headers": dict(e.response.headers),
                "data": {},
                "error": str(e)
            }
        except Exception as e:
            return {
                "status_code": 500,
                "headers": {},
                "data": {},
                "error": str(e)
            }
    
    async def get_json(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """Make GET request with JSON response"""
        try:
            response = await self.client.get(
                url=url,
                headers=headers or {},
                params=params
            )
            response.raise_for_status()
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "data": response.json() if response.content else {}
            }
        except httpx.HTTPStatusError as e:
            return {
                "status_code": e.response.status_code,
                "headers": dict(e.response.headers),
                "data": {},
                "error": str(e)
            }
        except Exception as e:
            return {
                "status_code": 500,
                "headers": {},
                "data": {},
                "error": str(e)
            }


class WebhookService:
    """SDK wrapper for webhook operations"""
    
    def __init__(self):
        self.http_service = HTTPRequestService()
    
    async def send_webhook(self, url: str, payload: Dict, headers: Optional[Dict] = None) -> Dict:
        """Send webhook payload to URL"""
        webhook_headers = {
            "Content-Type": "application/json",
            "User-Agent": "WeQ-Backend/1.0.0"
        }
        
        if headers:
            webhook_headers.update(headers)
        
        return await self.http_service.post_json(url, webhook_headers, payload)


# Factory functions for creating service instances
def create_email_service(config: Dict) -> EmailService:
    """Create email service from configuration"""
    return EmailService(
        smtp_host=config.get("SMTP_HOST"),
        smtp_port=int(config.get("SMTP_PORT", 587)),
        smtp_user=config.get("SMTP_USER"),
        smtp_password=config.get("SMTP_PASSWORD")
    )


def create_sms_service(config: Dict) -> SMSService:
    """Create SMS service from configuration"""
    return SMSService(
        account_sid=config.get("TWILIO_ACCOUNT_SID"),
        auth_token=config.get("TWILIO_AUTH_TOKEN"),
        from_number=config.get("TWILIO_FROM_NUMBER")
    )


def create_http_service() -> HTTPRequestService:
    """Create HTTP request service"""
    return HTTPRequestService()


def create_webhook_service() -> WebhookService:
    """Create webhook service"""
    return WebhookService()
