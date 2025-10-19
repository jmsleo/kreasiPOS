from flask import render_template, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from functools import wraps
from . import bp
from app.models import Tenant
from .. import db

def superadmin_required(f):
    """Decorator untuk memastikan hanya superadmin yang bisa mengakses route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        
        # Periksa apakah atribut is_superadmin ada dan True
        if not hasattr(current_user, 'is_superadmin') or not current_user.is_superadmin:
            abort(403)  # Forbidden
        
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/dashboard')
@login_required
@superadmin_required
def dashboard():
    """Halaman utama dasbor superadmin untuk mengelola tenant."""
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    return render_template('superadmin/dashboard.html', tenants=tenants, title="Superadmin Dashboard")

@bp.route('/tenants/<string:tenant_id>/toggle-status', methods=['POST'])
@login_required
@superadmin_required
def toggle_tenant_status(tenant_id):
    """Mengubah status aktif/non-aktif tenant."""
    tenant = Tenant.query.get_or_404(tenant_id)
    tenant.is_active = not tenant.is_active
    db.session.commit()
    status = "activated" if tenant.is_active else "deactivated"
    flash(f'Tenant "{tenant.name}" has been {status}.', 'success')
    return redirect(url_for('superadmin.dashboard'))
