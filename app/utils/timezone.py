from datetime import datetime
import pytz
from flask import current_app

def get_local_timezone():
    """Get the configured timezone for the application"""
    timezone_name = current_app.config.get('TIMEZONE', 'Asia/Jakarta')
    return pytz.timezone(timezone_name)

def utc_to_local(utc_dt):
    """Convert UTC datetime to local timezone"""
    if utc_dt is None:
        return None
    
    if utc_dt.tzinfo is None:
        # Assume UTC if no timezone info
        utc_dt = pytz.utc.localize(utc_dt)
    
    local_tz = get_local_timezone()
    return utc_dt.astimezone(local_tz)

def local_to_utc(local_dt):
    """Convert local datetime to UTC"""
    if local_dt is None:
        return None
    
    local_tz = get_local_timezone()
    
    if local_dt.tzinfo is None:
        # Assume local timezone if no timezone info
        local_dt = local_tz.localize(local_dt)
    
    return local_dt.astimezone(pytz.utc)

def now_local():
    """Get current datetime in local timezone"""
    local_tz = get_local_timezone()
    return datetime.now(local_tz)

def now_utc():
    """Get current datetime in UTC"""
    return datetime.now(pytz.utc)

def format_local_datetime(utc_dt, format_str='%Y-%m-%d %H:%M:%S'):
    """Format UTC datetime as local timezone string"""
    if utc_dt is None:
        return ''
    
    local_dt = utc_to_local(utc_dt)
    return local_dt.strftime(format_str)

def format_local_date(utc_dt, format_str='%Y-%m-%d'):
    """Format UTC datetime as local date string"""
    if utc_dt is None:
        return ''
    
    local_dt = utc_to_local(utc_dt)
    return local_dt.strftime(format_str)

def format_local_time(utc_dt, format_str='%H:%M'):
    """Format UTC datetime as local time string"""
    if utc_dt is None:
        return ''
    
    local_dt = utc_to_local(utc_dt)
    return local_dt.strftime(format_str)