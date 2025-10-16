from flask import request, g
from app.models import Tenant
from app import db

def tenant_middleware():
    """Middleware untuk menangani multi-tenancy berdasarkan subdomain atau header"""
    g.tenant = None
    
    # Cek subdomain untuk identifikasi tenant
    host_parts = request.host.split('.')
    if len(host_parts) > 2:
        subdomain = host_parts[0]
        if subdomain and subdomain != 'www':
            g.tenant = Tenant.query.filter_by(subdomain=subdomain, is_active=True).first()
    
    # Fallback: cek header X-Tenant-ID
    if not g.tenant and request.headers.get('X-Tenant-ID'):
        tenant_id = request.headers.get('X-Tenant-ID')
        g.tenant = Tenant.query.filter_by(id=tenant_id, is_active=True).first()
    
    # Fallback: tenant default untuk development
    if not g.tenant:
        g.tenant = Tenant.query.filter_by(is_default=True).first()

def switch_tenant_schema(tenant_id):
    """Switch database schema berdasarkan tenant"""
    if tenant_id:
        db.session.execute(f"SET search_path TO tenant_{tenant_id}, public")

def create_tenant_schema(tenant):
    """Membuat schema baru untuk tenant"""
    schema_name = f"tenant_{tenant.id}"
    
    # Create schema
    db.session.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    
    # Set search path dan buat tables
    db.session.execute(f"SET search_path TO {schema_name}")
    db.metadata.create_all(bind=db.engine)
    
    # Kembali ke schema public
    db.session.execute("SET search_path TO public")
    db.session.commit()