from app.models import MaintenanceSettings, db, User
from datetime import datetime, timedelta

class MaintenanceService:
    @staticmethod
    def get_settings():
        """Get atau create maintenance settings"""
        settings = MaintenanceSettings.query.first()
        if not settings:
            settings = MaintenanceSettings()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    @staticmethod
    def is_maintenance_mode():
        """Check if maintenance mode is active"""
        settings = MaintenanceService.get_settings()
        return settings.is_active
    
    @staticmethod
    def enable_maintenance(message="System under maintenance", estimated_minutes=60, allowed_emails=None):
        """Enable maintenance mode"""
        settings = MaintenanceService.get_settings()
        
        settings.is_active = True
        settings.message = message
        settings.start_time = datetime.utcnow()
        settings.estimated_end_time = datetime.utcnow() + timedelta(minutes=estimated_minutes)
        settings.allowed_emails = allowed_emails or []
        settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        return settings
    
    @staticmethod
    def disable_maintenance():
        """Disable maintenance mode"""
        settings = MaintenanceService.get_settings()
        
        settings.is_active = False
        settings.updated_at = datetime.utcnow()
        
        db.session.commit()
        return settings
    
    @staticmethod
    def can_user_access(user):
        """Check if user can access during maintenance berdasarkan email"""
        if not user or not user.is_authenticated:
            return False
            
        settings = MaintenanceService.get_settings()
        user_email = user.email.lower().strip()
        allowed_emails = [email.lower().strip() for email in (settings.allowed_emails or [])]
        
        return user_email in allowed_emails
    
    @staticmethod
    def get_maintenance_info():
        """Get maintenance information"""
        settings = MaintenanceService.get_settings()
        return settings.to_dict()
    
    @staticmethod
    def add_allowed_email(email):
        """Add email to whitelist"""
        settings = MaintenanceService.get_settings()
        email = email.lower().strip()
        
        if email not in settings.allowed_emails:
            settings.allowed_emails.append(email)
            settings.updated_at = datetime.utcnow()
            db.session.commit()
        
        return settings
    
    @staticmethod
    def remove_allowed_email(email):
        """Remove email from whitelist"""
        settings = MaintenanceService.get_settings()
        email = email.lower().strip()
        
        if email in settings.allowed_emails:
            settings.allowed_emails.remove(email)
            settings.updated_at = datetime.utcnow()
            db.session.commit()
        
        return settings
    
    @staticmethod
    def get_allowed_users():
        """Get list of users who are allowed access"""
        settings = MaintenanceService.get_settings()
        allowed_emails = settings.allowed_emails or []
        
        # Get user objects for the allowed emails
        users = User.query.filter(User.email.in_(allowed_emails)).all()
        return users