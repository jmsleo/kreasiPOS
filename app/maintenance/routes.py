from flask import render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.maintenance import bp
from app.services.maintenance_service import MaintenanceService
from datetime import datetime, timedelta

@bp.route('/api/maintenance/status')
def maintenance_status():
    """API untuk cek status maintenance"""
    info = MaintenanceService.get_maintenance_info()
    return jsonify({
        'maintenance_mode': MaintenanceService.is_maintenance_mode(),
        'maintenance_info': info
    })

@bp.route('/maintenance')
def maintenance_page():
    """Maintenance page"""
    info = MaintenanceService.get_maintenance_info()
    return render_template('errors/maintenance.html', maintenance_info=info), 503

@bp.route('/admin/maintenance', methods=['GET', 'POST'])
@login_required
def admin_maintenance():
    """Admin panel untuk manage maintenance mode dengan email whitelist"""
    if not current_user.is_admin:
        flash('Unauthorized access', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        message = request.form.get('message', 'System under maintenance')
        estimated_minutes = int(request.form.get('estimated_minutes', 60))
        
        if action == 'enable':
            # Automatically add current admin to whitelist
            allowed_emails = [current_user.email]
            
            # Add any additional emails from form
            additional_emails = request.form.get('initial_emails', '')
            if additional_emails:
                email_list = [email.strip() for email in additional_emails.split(',') if email.strip()]
                allowed_emails.extend(email_list)
            
            MaintenanceService.enable_maintenance(
                message=message,
                estimated_minutes=estimated_minutes,
                allowed_emails=allowed_emails
            )
            flash('Maintenance mode enabled', 'success')
            
        elif action == 'disable':
            MaintenanceService.disable_maintenance()
            flash('Maintenance mode disabled', 'success')
        
        elif action == 'add_email':
            email = request.form.get('email', '').strip()
            if email:
                MaintenanceService.add_allowed_email(email)
                flash(f'Email {email} added to whitelist', 'success')
            else:
                flash('Please enter a valid email', 'error')
        
        elif action == 'remove_email':
            email = request.form.get('email', '').strip()
            if email:
                MaintenanceService.remove_allowed_email(email)
                flash(f'Email {email} removed from whitelist', 'success')
            else:
                flash('Please enter a valid email', 'error')
        
        return redirect(url_for('maintenance.admin_maintenance'))
    
    maintenance_info = MaintenanceService.get_maintenance_info()
    allowed_users = MaintenanceService.get_allowed_users()
    
    return render_template('admin/maintenance.html', 
                         maintenance_info=maintenance_info,
                         allowed_users=allowed_users)

@bp.route('/api/admin/maintenance/toggle', methods=['POST'])
@login_required
def api_toggle_maintenance():
    """API untuk toggle maintenance mode"""
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    if MaintenanceService.is_maintenance_mode():
        MaintenanceService.disable_maintenance()
        return jsonify({'status': 'disabled', 'message': 'Maintenance mode disabled'})
    else:
        message = data.get('message', 'System under maintenance')
        estimated_minutes = data.get('estimated_minutes', 60)
        allowed_emails = [current_user.email]  # Always allow current admin
        
        MaintenanceService.enable_maintenance(
            message=message,
            estimated_minutes=estimated_minutes,
            allowed_emails=allowed_emails
        )
        return jsonify({'status': 'enabled', 'message': 'Maintenance mode enabled'})

@bp.route('/api/admin/maintenance/emails', methods=['POST'])
@login_required
def api_manage_emails():
    """API untuk manage email whitelist"""
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    action = data.get('action')
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    if action == 'add':
        MaintenanceService.add_allowed_email(email)
        return jsonify({'status': 'success', 'message': f'Email {email} added to whitelist'})
    
    elif action == 'remove':
        MaintenanceService.remove_allowed_email(email)
        return jsonify({'status': 'success', 'message': f'Email {email} removed from whitelist'})
    
    else:
        return jsonify({'error': 'Invalid action'}), 400