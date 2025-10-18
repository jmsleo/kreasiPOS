from flask import request, g, abort
from app.models import Tenant
from app import db
from functools import wraps
from flask_login import current_user

def tenant_middleware():
    """Middleware to handle multi-tenancy based on subdomain or header"""
    g.tenant = None
    
    # Check subdomain for tenant identification
    host_parts = request.host.split('.')
    if len(host_parts) > 2:
        subdomain = host_parts[0]
        if subdomain and subdomain != 'www':
            g.tenant = Tenant.query.filter_by(subdomain=subdomain, is_active=True).first()
    
    # Fallback: check X-Tenant-ID header
    if not g.tenant and request.headers.get('X-Tenant-ID'):
        tenant_id = request.headers.get('X-Tenant-ID')
        g.tenant = Tenant.query.filter_by(id=tenant_id, is_active=True).first()
    
    # Fallback: default tenant for development
    if not g.tenant:
        g.tenant = Tenant.query.filter_by(is_default=True).first()

def switch_tenant_schema(tenant_id):
    """Switch database schema based on tenant"""
    if tenant_id:
        db.session.execute(f"SET search_path TO tenant_{tenant_id}, public")

def create_tenant_schema(tenant):
    """Create a new schema for a tenant"""
    schema_name = f"tenant_{tenant.id}"
    
    # Create schema
    db.session.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    
    # Set search path and create tables
    db.session.execute(f"SET search_path TO {schema_name}")
    db.metadata.create_all(bind=db.engine)
    
    # Revert to public schema
    db.session.execute("SET search_path TO public")
    db.session.commit()

def tenant_required(f):
    """Decorator to ensure a user is associated with a tenant."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.tenant_id:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function