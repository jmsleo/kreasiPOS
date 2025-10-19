from datetime import datetime
import pytz
from flask import current_app, session
from flask_login import current_user

def get_user_timezone():
    """Get the timezone for the current user, defaulting to the application's timezone."""
    # First, try to get timezone from the logged-in user's settings if available
    if current_user and current_user.is_authenticated and hasattr(current_user, 'timezone') and current_user.timezone:
        timezone_name = current_user.timezone
    # Fallback to session if you store it there for non-logged-in users
    elif 'timezone' in session:
        timezone_name = session['timezone']
    # Default to the application's configuration
    else:
        timezone_name = current_app.config.get('TIMEZONE', 'Asia/Jakarta')
    
    try:
        return pytz.timezone(timezone_name)
    except pytz.UnknownTimeZoneError:
        # Fallback to a default timezone if the user's setting is invalid
        return pytz.timezone(current_app.config.get('TIMEZONE', 'Asia/Jakarta'))

def convert_utc_to_user_timezone(utc_dt):
    """Convert a UTC datetime object to the user's local timezone."""
    if utc_dt is None:
        return None
    
    if utc_dt.tzinfo is None:
        # Assume UTC if no timezone info is present
        utc_dt = pytz.utc.localize(utc_dt)
    
    local_tz = get_user_timezone()
    return utc_dt.astimezone(local_tz)

def local_to_utc(local_dt):
    """Convert local datetime to UTC"""
    if local_dt is None:
        return None
    
    local_tz = get_user_timezone()
    
    if local_dt.tzinfo is None:
        # Assume local timezone if no timezone info
        local_dt = local_tz.localize(local_dt)
    
    return local_dt.astimezone(pytz.utc)

def now_local():
    """Get current datetime in local timezone"""
    local_tz = get_user_timezone()
    return datetime.now(local_tz)

def now_utc():
    """Get current datetime in UTC"""
    return datetime.now(pytz.utc)

def format_local_datetime(utc_dt, format_str='%Y-%m-%d %H:%M:%S'):
    """Format UTC datetime as local timezone string"""
    if utc_dt is None:
        return ''
    
    local_dt = convert_utc_to_user_timezone(utc_dt)
    return local_dt.strftime(format_str)

def format_local_date(utc_dt, format_str='%Y-%m-%d'):
    """Format UTC datetime as local date string"""
    if utc_dt is None:
        return ''
    
    local_dt = convert_utc_to_user_timezone(utc_dt)
    return local_dt.strftime(format_str)

def format_local_time(utc_dt, format_str='%H:%M'):
    """Format UTC datetime as local time string"""
    if utc_dt is None:
        return ''
    
    local_dt = convert_utc_to_user_timezone(utc_dt)
    return local_dt.strftime(format_str)