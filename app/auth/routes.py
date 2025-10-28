from flask import render_template, redirect, url_for, flash, request, session, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm, ForgotPasswordForm, ResetPasswordForm
from app.models import User, Tenant
from app import db, limiter
from app.services.postmark_service import postmark_service  # Import Postmark service
import random
import string
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Cari user berdasarkan EMAIL
        user = User.query.filter_by(email=form.email.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('auth.login'))
        
        # PERBAIKAN: Cek apakah user aktif terlebih dahulu
        if not user.is_active:
            flash('Your account has been deactivated. Please contact administrator.', 'warning')
            return redirect(url_for('auth.login'))
        
        # PERBAIKAN: Cek tenant hanya jika user bukan superadmin
        if not user.is_superadmin:
            if not user.tenant:
                flash('Your account is not associated with any business. Please contact administrator.', 'warning')
                return redirect(url_for('auth.login'))
            
            if not user.tenant.is_active:
                flash('Your business account has been deactivated. Please contact administrator.', 'warning')
                return redirect(url_for('auth.login'))
        
        # Login user dengan atau tanpa remember me
        login_user(user, remember=form.remember_me.data)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        session['login_time'] = datetime.utcnow().isoformat()
        
        flash('Login successful!', 'success')
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('dashboard.index')
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)

@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            print(f"Register attempt: Store: {form.store_name.data}, User: {form.username.data}")
            
            # Create tenant (store) - Biarkan database generate ID
            tenant = Tenant(
                name=form.store_name.data,
                email=form.email.data,
                phone=form.phone.data,
                subdomain=form.store_name.data.lower().replace(' ', '-')[:45],
                is_active=True,
                is_default=False
            )
            db.session.add(tenant)
            db.session.flush()  # Get tenant ID
            
            print(f"Tenant created with ID: {tenant.id}")
            
            # Create admin user for this tenant - Biarkan database generate ID
            user = User(
                username=form.username.data,
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                role='admin',  # Set sebagai admin untuk user pertama
                is_active=True,
                tenant_id=tenant.id
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            # Kirim welcome email menggunakan Postmark
            try:
                success = postmark_service.send_welcome_email(
                    to_email=user.email,
                    store_name=tenant.name,
                    username=user.username
                )
                if not success:
                    logger.warning(f"Welcome email failed to send to {user.email}, but registration was successful")
            except Exception as e:
                logger.error(f"Error sending welcome email: {str(e)}")
                # Jangan gagalkan registrasi hanya karena email gagal
            
            print("Registration successful!")
            flash('Registration successful! Please login to your account.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {str(e)}")
            if "unique constraint" in str(e).lower():
                if "username" in str(e).lower():
                    flash('Username already exists. Please choose a different username.', 'danger')
                elif "email" in str(e).lower():
                    flash('Email already exists. Please use a different email address.', 'danger')
                else:
                    flash('Store name or email already exists. Please choose different values.', 'danger')
            else:
                flash('Registration failed. Please try again.', 'danger')
    
    return render_template('auth/register.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Generate OTP
            otp = generate_otp()
            session['reset_otp'] = otp
            session['reset_email'] = user.email
            session['reset_attempts'] = 0
            session['reset_created'] = datetime.utcnow().isoformat()
            
            # Send OTP via Postmark
            try:
                success = postmark_service.send_otp_email(
                    to_email=user.email,
                    otp_code=otp,
                    user_name=user.username or user.first_name or "User"
                )
                
                if success:
                    flash('OTP sent to your email address', 'info')
                    logger.info(f"OTP email sent successfully to {user.email}")
                else:
                    flash('Failed to send OTP. Please try again.', 'danger')
                    logger.error(f"Failed to send OTP email to {user.email}")
                    return redirect(url_for('auth.forgot_password'))
                
            except Exception as e:
                logger.error(f"Error sending OTP email to {user.email}: {str(e)}")
                flash('Failed to send OTP. Please try again.', 'danger')
                return redirect(url_for('auth.forgot_password'))
            
            return redirect(url_for('auth.reset_password'))
        else:
            # Untuk keamanan, tetap tampilkan pesan sukses meskipun email tidak ditemukan
            flash('If an account with that email exists, an OTP has been sent.', 'info')
            return redirect(url_for('auth.reset_password'))
    
    return render_template('auth/forgot_password.html', form=form)

@bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def reset_password():
    form = ResetPasswordForm()
    
    # Check if OTP session exists
    if 'reset_email' not in session:
        flash('Password reset session expired', 'warning')
        return redirect(url_for('auth.forgot_password'))
    
    # Check OTP expiration (10 minutes)
    reset_created = datetime.fromisoformat(session.get('reset_created'))
    if (datetime.utcnow() - reset_created).total_seconds() > 600:
        session.pop('reset_otp', None)
        session.pop('reset_email', None)
        session.pop('reset_attempts', None)
        session.pop('reset_created', None)
        flash('OTP has expired', 'warning')
        return redirect(url_for('auth.forgot_password'))
    
    if form.validate_on_submit():
        # Check attempts
        session['reset_attempts'] = session.get('reset_attempts', 0) + 1
        if session['reset_attempts'] > 5:
            session.pop('reset_otp', None)
            session.pop('reset_email', None)
            session.pop('reset_attempts', None)
            session.pop('reset_created', None)
            flash('Too many attempts. Please start over.', 'danger')
            return redirect(url_for('auth.forgot_password'))
        
        if session.get('reset_otp') == form.otp.data:
            user = User.query.filter_by(email=session['reset_email']).first()
            if user:
                user.set_password(form.password.data)
                db.session.commit()
                
                # Clear session
                session.pop('reset_otp', None)
                session.pop('reset_email', None)
                session.pop('reset_attempts', None)
                session.pop('reset_created', None)
                
                flash('Password reset successfully! Please login.', 'success')
                return redirect(url_for('auth.login'))
        
        flash('Invalid OTP', 'danger')
    
    return render_template('auth/reset_password.html', form=form)