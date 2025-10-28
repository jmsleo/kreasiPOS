import os
import logging
from postmarker.core import PostmarkClient
from flask import current_app

# Setup logging
logger = logging.getLogger(__name__)

class PostmarkService:
    def __init__(self):
        self.api_key = current_app.config.get('POSTMARK_API_KEY')
        self.from_email = current_app.config.get('POSTMARK_FROM_EMAIL')
        self.otp_template_id = current_app.config.get('POSTMARK_OTP_TEMPLATE_ID')
        self.welcome_template_id = current_app.config.get('POSTMARK_WELCOME_TEMPLATE_ID')
        self.logo_url = current_app.config.get('LOGO_URL')
        self.app_url = current_app.config.get('APP_URL', 'https://your-domain.com')
        self.client = None
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Postmark client dengan error handling"""
        try:
            if not all([self.api_key, self.from_email]):
                logger.error("Postmark configuration missing: API_KEY or FROM_EMAIL")
                return
            
            self.client = PostmarkClient(server_token=self.api_key)
            logger.info("Postmark client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Postmark client: {str(e)}")
    
    def send_otp_email(self, to_email, otp_code, user_name=None):
        """Kirim email OTP menggunakan template Postmark"""
        if not self.client:
            logger.error("Postmark client not available")
            return False
        
        if not self.otp_template_id:
            logger.error("OTP template ID not configured")
            return False
        
        try:
            template_model = {
                "otp_code": otp_code,
                "user_name": user_name or "User",
                "validity_minutes": 10,
                "support_email": self.from_email,
                "app_url": self.app_url,
                "logo_url": self.logo_url
            }
            
            response = self.client.emails.send_with_template(
                From=self.from_email,
                To=to_email,
                TemplateId=int(self.otp_template_id),
                TemplateModel=template_model
            )
            
            if response.get('ErrorCode', 0) == 0:
                logger.info(f"OTP email sent successfully to {to_email}. MessageID: {response.get('MessageID')}")
                return True
            else:
                logger.error(f"Postmark error for {to_email}: {response.get('Message')}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send OTP email to {to_email}: {str(e)}")
            return False
    
    def send_welcome_email(self, to_email, store_name, username):
        """Kirim email welcome menggunakan template Postmark"""
        if not self.client:
            logger.error("Postmark client not available")
            return False
        
        if not self.welcome_template_id:
            logger.error("Welcome template ID not configured")
            return False
        
        try:
            template_model = {
                "store_name": store_name,
                "username": username,
                "login_url": f"{self.app_url}/auth/login",
                "support_email": self.from_email,
                "app_url": self.app_url,
                "logo_url": self.logo_url
            }
            
            response = self.client.emails.send_with_template(
                From=self.from_email,
                To=to_email,
                TemplateId=int(self.welcome_template_id),
                TemplateModel=template_model
            )
            
            if response.get('ErrorCode', 0) == 0:
                logger.info(f"Welcome email sent successfully to {to_email}. MessageID: {response.get('MessageID')}")
                return True
            else:
                logger.error(f"Postmark error for {to_email}: {response.get('Message')}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send welcome email to {to_email}: {str(e)}")
            return False

# Global instance
postmark_service = PostmarkService()