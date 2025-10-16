from flask import render_template, flash, redirect, url_for, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import uuid
import os
from datetime import datetime
from . import bp
from .forms import MarketplaceItemForm, RestockOrderForm, RestockVerificationForm, PaymentMethodForm,TenantAddressForm
from ..models import MarketplaceItem, Product, db, PaymentMethod,RestockOrder, RestockStatus, Tenant
from ..superadmin.routes import superadmin_required
from app.services.s3_service import S3Service  # Import S3Service

# --- Rute untuk Tenant ---
@bp.route('/')
@login_required
def index():
    """Halaman Marketplace untuk dilihat oleh Tenant."""
    items = MarketplaceItem.query.filter(MarketplaceItem.stock > 0).order_by(MarketplaceItem.created_at.desc()).all()
    
    # Pastikan query payment methods ini ada dan benar
    payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
    
    return render_template('marketplace/index.html', 
                         items=items, 
                         payment_methods=payment_methods,  # Pastikan ini dikirim
                         title="Marketplace")
@bp.route('/restock/<string:item_id>', methods=['GET', 'POST'])
@login_required
def restock_item(item_id):
    """Proses restock item dengan pembayaran dan verifikasi."""
    try:
        item_to_restock = MarketplaceItem.query.get_or_404(item_id)
        
        # Validasi tenant
        if not current_user.tenant_id:
            flash('Tenant tidak ditemukan untuk user ini.', 'danger')
            return redirect(url_for('marketplace.index'))
            
        tenant = Tenant.query.get(current_user.tenant_id)
        if not tenant:
            flash('Tenant tidak ditemukan.', 'danger')
            return redirect(url_for('marketplace.index'))
        
        form = RestockOrderForm()
        payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
        
        # Handle GET request - set default values
        if request.method == 'GET':
            if tenant.address:
                form.shipping_address.data = tenant.address
                form.shipping_city.data = tenant.city
                form.shipping_postal_code.data = tenant.postal_code
                form.shipping_phone.data = tenant.phone
        
        # Handle POST request
        if form.validate_on_submit():
            try:
                quantity = form.quantity.data
                total_amount = item_to_restock.price * quantity
                
                # Validasi stok
                if quantity > item_to_restock.stock:
                    flash(f'Stok tidak tersedia. Hanya tersisa {item_to_restock.stock} item.', 'danger')
                    return render_template('marketplace/restock.html', 
                                        item=item_to_restock, 
                                        form=form,
                                        payment_methods=payment_methods,
                                        tenant=tenant,
                                        title=f"Restock {item_to_restock.name}")
                
                # Validasi manual untuk file upload
                if not form.payment_proof.data or form.payment_proof.data.filename == '':
                    flash('Bukti pembayaran wajib diupload.', 'danger')
                    return render_template('marketplace/restock.html', 
                                        item=item_to_restock, 
                                        form=form,
                                        payment_methods=payment_methods,
                                        tenant=tenant,
                                        title=f"Restock {item_to_restock.name}")
                
                # Validasi file type
                allowed_extensions = ['jpg', 'jpeg', 'png', 'pdf']
                file_ext = form.payment_proof.data.filename.rsplit('.', 1)[1].lower() if '.' in form.payment_proof.data.filename else ''
                if file_ext not in allowed_extensions:
                    flash('Format file tidak didukung. Gunakan JPG, PNG, atau PDF.', 'danger')
                    return render_template('marketplace/restock.html', 
                                        item=item_to_restock, 
                                        form=form,
                                        payment_methods=payment_methods,
                                        tenant=tenant,
                                        title=f"Restock {item_to_restock.name}")
                
                # Handle upload bukti pembayaran
                s3_service = S3Service()
                payment_proof_url = s3_service.upload_product_image(
                    form.payment_proof.data, 
                    f"payment_proof_{current_user.tenant_id}_{uuid.uuid4().hex[:8]}"
                )
                
                # Tentukan alamat pengiriman
                if form.use_default_address.data and tenant.address:
                    shipping_address = tenant.address
                    shipping_city = tenant.city
                    shipping_postal_code = tenant.postal_code
                    shipping_phone = tenant.phone
                else:
                    shipping_address = form.shipping_address.data
                    shipping_city = form.shipping_city.data
                    shipping_postal_code = form.shipping_postal_code.data
                    shipping_phone = form.shipping_phone.data
                
                # Validasi alamat pengiriman
                if not shipping_address or not shipping_city:
                    flash('Alamat pengiriman wajib diisi.', 'danger')
                    return render_template('marketplace/restock.html', 
                                        item=item_to_restock, 
                                        form=form,
                                        payment_methods=payment_methods,
                                        tenant=tenant,
                                        title=f"Restock {item_to_restock.name}")
                
                # Buat restock order
                restock_order = RestockOrder(
                    id=str(uuid.uuid4()),
                    tenant_id=current_user.tenant_id,
                    marketplace_item_id=item_id,
                    quantity=quantity,
                    total_amount=total_amount,
                    shipping_address=shipping_address,
                    shipping_city=shipping_city,
                    shipping_postal_code=shipping_postal_code,
                    shipping_phone=shipping_phone,
                    payment_proof_url=payment_proof_url,
                    notes=form.notes.data,
                    status=RestockStatus.PENDING
                )
                
                db.session.add(restock_order)
                db.session.commit()
                
                flash('Order restock berhasil dibuat. Silakan tunggu verifikasi admin.', 'success')
                return redirect(url_for('marketplace.restock_orders'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating restock order: {str(e)}")
                flash(f'Error creating restock order: {str(e)}', 'danger')
        
        # Untuk debugging - log form errors
        if form.errors:
            current_app.logger.warning(f"Form validation errors: {form.errors}")
        
        # Untuk GET request atau form tidak valid
        return render_template('marketplace/restock.html', 
                             item=item_to_restock, 
                             form=form,
                             payment_methods=payment_methods,
                             tenant=tenant,
                             title=f"Restock {item_to_restock.name}")
                             
    except Exception as e:
        current_app.logger.error(f"Error in restock_item route: {str(e)}")
        flash('Terjadi error saat mengakses halaman restock.', 'danger')
        return redirect(url_for('marketplace.index'))

@bp.route('/restock-orders')
@login_required
def restock_orders():
    """Menampilkan riwayat restock orders tenant."""
    status_filter = request.args.get('status')
    
    query = RestockOrder.query.filter_by(tenant_id=current_user.tenant_id)
    
    if status_filter:
        query = query.filter_by(status=RestockStatus(status_filter))
    
    orders = query.order_by(RestockOrder.created_at.desc()).all()
    
    return render_template('marketplace/restock_orders.html', 
                         orders=orders,
                         title="My Restock Orders")

@bp.route('/my-address', methods=['GET', 'POST'])
@login_required
def my_address():
    """Halaman untuk mengelola alamat tenant"""
    tenant = Tenant.query.get(current_user.tenant_id)
    form = TenantAddressForm(obj=tenant)
    
    if form.validate_on_submit():
        try:
            tenant.address = form.address.data
            tenant.city = form.city.data
            tenant.postal_code = form.postal_code.data
            tenant.phone = form.phone.data
            tenant.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Alamat berhasil diperbarui!', 'success')
            return redirect(url_for('marketplace.my_address'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating address: {str(e)}")
            flash(f'Error updating address: {str(e)}', 'danger')
    
    return render_template('marketplace/my_address.html', 
                         form=form, 
                         tenant=tenant,
                         title="My Address")

@bp.route('/order/<string:order_id>')
@login_required
def order_detail(order_id):
    """Halaman detail untuk order tertentu."""
    order = RestockOrder.query.filter_by(
        id=order_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    return render_template('marketplace/order_detail.html', 
                         order=order,
                         title=f"Order Details - {order.marketplace_item.name}")

# --- Rute untuk Superadmin ---

@bp.route('/manage')
@login_required
@superadmin_required
def manage():
    """Halaman Superadmin untuk mengelola semua item marketplace."""
    filter_type = request.args.get('filter', 'all')
    
    query = MarketplaceItem.query
    
    if filter_type == 'in_stock':
        query = query.filter(MarketplaceItem.stock > 0)
    elif filter_type == 'out_of_stock':
        query = query.filter(MarketplaceItem.stock == 0)
    
    items = query.order_by(MarketplaceItem.name).all()
    
    # Hitung statistik
    total_items = len(items)
    in_stock_count = len([item for item in items if item.stock > 0])
    out_of_stock_count = len([item for item in items if item.stock == 0])
    total_value = sum(item.price * item.stock for item in items)
    
    return render_template('marketplace/manage.html', 
                         items=items,
                         total_items=total_items,
                         in_stock_count=in_stock_count,
                         out_of_stock_count=out_of_stock_count,
                         total_value="${:,.2f}".format(total_value),
                         title="Manage Marketplace")

@bp.route('/manage/new', methods=['GET', 'POST'])
@login_required
@superadmin_required
def create_item():
    """Form untuk membuat item marketplace baru."""
    form = MarketplaceItemForm()
    
    if form.validate_on_submit():
        try:
            new_item = MarketplaceItem(
                id=str(uuid.uuid4()),
                name=form.name.data,
                description=form.description.data,
                price=form.price.data,
                stock=form.stock.data,
                sku=form.sku.data
            )
            
            # Handle image upload
            if form.image.data:
                s3_service = S3Service()
                image_url = s3_service.upload_product_image(form.image.data, f"marketplace_{new_item.id}")
                new_item.image_url = image_url
            
            db.session.add(new_item)
            db.session.commit()
            
            flash(f'Item "{new_item.name}" has been created.', 'success')
            return redirect(url_for('marketplace.manage'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating marketplace item: {str(e)}")
            flash(f'Error creating item: {str(e)}', 'danger')
    
    return render_template('marketplace/create_edit_item.html', 
                         form=form, 
                         title="Create Marketplace Item", 
                         legend="New Marketplace Item")

@bp.route('/manage/edit/<string:item_id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def edit_item(item_id):
    """Form untuk mengedit item marketplace yang ada."""
    item = MarketplaceItem.query.get_or_404(item_id)
    form = MarketplaceItemForm(obj=item)
    
    # Pass the object to template for displaying current image
    form._obj = item
    
    if form.validate_on_submit():
        try:
            item.name = form.name.data
            item.description = form.description.data
            item.price = form.price.data
            item.stock = form.stock.data
            item.sku = form.sku.data

            # Handle image upload
            if form.image.data:
                s3_service = S3Service()
                image_url = s3_service.upload_product_image(form.image.data, f"marketplace_{item.id}")
                
                # Hapus gambar lama jika ada
                if item.image_url:
                    try:
                        old_image_url = item.image_url
                        if 'amazonaws.com/' in old_image_url:
                            object_name = old_image_url.split('amazonaws.com/')[1]
                            s3_service.delete_file(object_name)
                    except Exception as e:
                        current_app.logger.warning(f"Could not delete old image: {str(e)}")
                
                item.image_url = image_url

            db.session.commit()
            flash(f'Item "{item.name}" has been updated.', 'success')
            return redirect(url_for('marketplace.manage'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating marketplace item: {str(e)}")
            flash(f'Error updating item: {str(e)}', 'danger')

    return render_template('marketplace/create_edit_item.html', 
                         form=form, 
                         title="Edit Marketplace Item", 
                         legend=f"Edit {item.name}")


@bp.route('/manage/delete/<string:item_id>', methods=['POST'])
@login_required
@superadmin_required
def delete_item(item_id):
    """Menghapus item dari marketplace."""
    item = MarketplaceItem.query.get_or_404(item_id)
    
    try:
        # Hapus gambar dari S3 jika ada
        if item.image_url:
            try:
                s3_service = S3Service()  # Inisialisasi di dalam function
                # Extract object name dari URL
                if 'amazonaws.com/' in item.image_url:
                    object_name = item.image_url.split('amazonaws.com/')[1]
                    s3_service.delete_file(object_name)
            except Exception as e:
                current_app.logger.warning(f"Could not delete image from S3: {str(e)}")
        
        # Hapus item dari database
        db.session.delete(item)
        db.session.commit()
        flash(f'Item "{item.name}" has been deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting marketplace item: {str(e)}")
        flash(f'Error deleting item: {str(e)}', 'danger')
    
    return redirect(url_for('marketplace.manage'))

@bp.route('/admin/restock-orders')
@login_required
@superadmin_required
def admin_restock_orders():
    """Halaman admin untuk memverifikasi restock orders."""
    status_filter = request.args.get('status', 'pending')
    
    query = RestockOrder.query
    
    if status_filter == 'pending':
        query = query.filter_by(status=RestockStatus.PENDING)
    elif status_filter == 'verified':
        query = query.filter_by(status=RestockStatus.VERIFIED)
    elif status_filter == 'rejected':
        query = query.filter_by(status=RestockStatus.REJECTED)
    
    orders = query.order_by(RestockOrder.created_at.desc()).all()
    
    return render_template('marketplace/admin_restock_orders.html', 
                         orders=orders,
                         status_filter=status_filter,
                         title="Manage Restock Orders")

@bp.route('/admin/restock-orders/<string:order_id>/verify', methods=['GET', 'POST'])
@login_required
@superadmin_required
def verify_restock_order(order_id):
    """Verifikasi restock order oleh admin."""
    restock_order = RestockOrder.query.get_or_404(order_id)
    form = RestockVerificationForm()
    
    if form.validate_on_submit():
        try:
            new_status = RestockStatus(form.status.data)
            restock_order.status = new_status
            restock_order.verified_by = current_user.id
            restock_order.verified_at = datetime.utcnow()
            restock_order.admin_notes = form.admin_notes.data
            
            # Jika status verified, tambahkan stok ke produk tenant
            if new_status == RestockStatus.VERIFIED:
                existing_product = Product.query.filter_by(
                    tenant_id=restock_order.tenant_id, 
                    name=restock_order.marketplace_item.name
                ).first()
                
                if existing_product:
                    existing_product.stock_quantity += restock_order.quantity
                else:
                    new_product = Product(
                        id=str(uuid.uuid4()),
                        name=restock_order.marketplace_item.name,
                        description=restock_order.marketplace_item.description,
                        price=restock_order.marketplace_item.price,
                        stock_quantity=restock_order.quantity,
                        sku=restock_order.marketplace_item.sku,
                        tenant_id=restock_order.tenant_id,
                        image_url=restock_order.marketplace_item.image_url
                    )
                    db.session.add(new_product)
                
                # Kurangi stok dari marketplace item
                restock_order.marketplace_item.stock -= restock_order.quantity
            
            db.session.commit()
            
            status_message = "verified" if new_status == RestockStatus.VERIFIED else "rejected"
            flash(f'Restock order has been {status_message}.', 'success')
            return redirect(url_for('marketplace.admin_restock_orders'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error verifying restock order: {str(e)}")
            flash(f'Error verifying restock order: {str(e)}', 'danger')
    
    return render_template('marketplace/verify_restock.html', 
                         order=restock_order,
                         form=form,
                         title="Verify Restock Order")

# --- Rute untuk Mengelola Payment Methods (Superadmin) ---

@bp.route('/admin/payment-methods')
@login_required
@superadmin_required
def payment_methods():
    """Kelola payment methods."""
    methods = PaymentMethod.query.order_by(PaymentMethod.created_at.desc()).all()
    return render_template('marketplace/payment_methods.html', 
                         methods=methods,
                         title="Payment Methods")

@bp.route('/admin/payment-methods/new', methods=['GET', 'POST'])
@login_required
@superadmin_required
def create_payment_method():
    """Create new payment method."""
    form = PaymentMethodForm()
    if form.validate_on_submit():
        try:
            new_method = PaymentMethod(
                id=str(uuid.uuid4()),
                name=form.name.data,
                account_number=form.account_number.data,
                account_name=form.account_name.data,
                is_active=form.is_active.data
            )
            
            # Handle QR code upload
            if form.qr_code.data:
                s3_service = S3Service()
                qr_code_url = s3_service.upload_product_image(
                    form.qr_code.data, 
                    f"qr_code_{new_method.id}"
                )
                new_method.qr_code_url = qr_code_url
            
            db.session.add(new_method)
            db.session.commit()
            
            flash('Payment method created successfully.', 'success')
            return redirect(url_for('marketplace.payment_methods'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating payment method: {str(e)}")
            flash(f'Error creating payment method: {str(e)}', 'danger')
    
    return render_template('marketplace/create_edit_payment_method.html', 
                         form=form, 
                         title="Create Payment Method")

@bp.route('/admin/payment-methods/edit/<string:method_id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def edit_payment_method(method_id):
    """Edit payment method."""
    method = PaymentMethod.query.get_or_404(method_id)
    form = PaymentMethodForm(obj=method)
    
    if form.validate_on_submit():
        try:
            method.name = form.name.data
            method.account_number = form.account_number.data
            method.account_name = form.account_name.data
            method.is_active = form.is_active.data

            # Handle QR code upload
            if form.qr_code.data:
                s3_service = S3Service()
                qr_code_url = s3_service.upload_product_image(
                    form.qr_code.data, 
                    f"qr_code_{method.id}"
                )
                # Hapus QR code lama jika ada
                if method.qr_code_url:
                    try:
                        old_qr_url = method.qr_code_url
                        if 'amazonaws.com/' in old_qr_url:
                            object_name = old_qr_url.split('amazonaws.com/')[1]
                            s3_service.delete_file(object_name)
                    except Exception as e:
                        current_app.logger.warning(f"Could not delete old QR code: {str(e)}")
                
                method.qr_code_url = qr_code_url

            db.session.commit()
            flash('Payment method updated successfully.', 'success')
            return redirect(url_for('marketplace.payment_methods'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating payment method: {str(e)}")
            flash(f'Error updating payment method: {str(e)}', 'danger')
    
    return render_template('marketplace/create_edit_payment_method.html', 
                         form=form, 
                         title="Edit Payment Method",
                         method=method)

@bp.route('/admin/payment-methods/delete/<string:method_id>', methods=['POST'])
@login_required
@superadmin_required
def delete_payment_method(method_id):
    """Delete payment method."""
    method = PaymentMethod.query.get_or_404(method_id)
    
    try:
        # Hapus QR code dari S3 jika ada
        if method.qr_code_url:
            try:
                s3_service = S3Service()
                if 'amazonaws.com/' in method.qr_code_url:
                    object_name = method.qr_code_url.split('amazonaws.com/')[1]
                    s3_service.delete_file(object_name)
            except Exception as e:
                current_app.logger.warning(f"Could not delete QR code from S3: {str(e)}")
        
        db.session.delete(method)
        db.session.commit()
        flash('Payment method deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting payment method: {str(e)}")
        flash(f'Error deleting payment method: {str(e)}', 'danger')
    
    return redirect(url_for('marketplace.payment_methods'))

