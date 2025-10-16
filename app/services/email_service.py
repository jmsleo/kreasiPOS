import smtplib
from email.mime.text import MIMEText  # Corrected from MimeText
from email.mime.multipart import MIMEMultipart  # Corrected from MimeMultipart
from flask import current_app
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = current_app.config.get('MAIL_SERVER')
        self.smtp_port = current_app.config.get('MAIL_PORT', 587)
        self.username = current_app.config.get('MAIL_USERNAME')
        self.password = current_app.config.get('MAIL_PASSWORD')
        self.use_tls = current_app.config.get('MAIL_USE_TLS', True)
    
    def send_otp_email(self, to_email, otp_code):
        """Kirim email OTP untuk reset password"""
        subject = "T-POS Enterprise - Password Reset OTP"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4e73df; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f8f9fc; }}
                .otp-code {{ font-size: 32px; font-weight: bold; text-align: center; color: #4e73df; margin: 20px 0; }}
                .footer {{ padding: 20px; text-align: center; color: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>T-POS Enterprise</h1>
                </div>
                <div class="content">
                    <h2>Password Reset Request</h2>
                    <p>You have requested to reset your password. Use the OTP code below:</p>
                    <div class="otp-code">{otp_code}</div>
                    <p>This OTP will expire in 10 minutes.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.now().year} T-POS Enterprise. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
    
    def send_welcome_email(self, to_email, store_name, username):
        """Kirim email welcome untuk tenant baru"""
        subject = f"Welcome to T-POS Enterprise - {store_name}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4e73df; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f8f9fc; }}
                .footer {{ padding: 20px; text-align: center; color: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to T-POS Enterprise!</h1>
                </div>
                <div class="content">
                    <h2>Hello {username},</h2>
                    <p>Welcome to T-POS Enterprise! Your store <strong>{store_name}</strong> has been successfully registered.</p>
                    <p>You can now start using our comprehensive POS system with features like:</p>
                    <ul>
                        <li>Real-time sales processing</li>
                        <li>Inventory management</li>
                        <li>Customer management</li>
                        <li>Detailed reporting</li>
                        <li>Hardware integration</li>
                    </ul>
                    <p>Login to your dashboard to get started.</p>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.now().year} T-POS Enterprise. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
    
    def send_email(self, to_email, subject, html_content):
        """Kirim email menggunakan SMTP"""
        try:
            # Create message
            msg = MIMEMultipart()  # Corrected from MimeMultipart
            msg['From'] = self.username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Attach HTML content
            msg.attach(MIMEText(html_content, 'html'))  # Corrected from MimeText
            
            # Connect to server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False