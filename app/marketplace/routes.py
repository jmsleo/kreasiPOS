from flask import render_template, flash, redirect, url_for, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import uuid
import os
from datetime import datetime
from . import bp
from .forms import MarketplaceItemForm, RestockOrderForm, RestockVerificationForm, PaymentMethodForm, TenantAddressForm
from ..models import DestinationType, MarketplaceItem, Product, RawMaterial, db, PaymentMethod,RestockOrder, RestockStatus, Tenant
from ..superadmin.routes import superadmin_required
from app.services.s3_service import S3Service
from app.services.cache_service import CacheService, ProductCacheService, cache_result

# --- Cache Configuration ---
MARKETPLACE_CACHE_TIMEOUT = 1800  # 30 menit untuk data marketplace
PRODUCT_CACHE_TIMEOUT = 900      # 15 menit untuk data produk
ORDER_CACHE_TIMEOUT = 600        # 10 menit untuk data order

# --- Helper Functions untuk Cache ---
def get_marketplace_cache_key(filter_type='all'):
    """Generate cache key untuk marketplace items"""
    return CacheService.get_cache_key('marketplace_items', filter_type)

def get_restock_orders_cache_key(tenant_id=None, status=None):
    """Generate cache key untuk restock orders"""
    if tenant_id:
        return CacheService.get_cache_key('restock_orders', status, tenant_id=tenant_id)
    return CacheService.get_cache_key('admin_restock_orders', status)

def get_payment_methods_cache_key():
    """Generate cache key untuk payment methods"""
    return CacheService.get_cache_key('payment_methods', 'active')

def invalidate_marketplace_cache():
    """Invalidate semua cache terkait marketplace"""
    CacheService.delete_pattern('marketplace_items:*')
    CacheService.delete_pattern('product_list:*')
    CacheService.delete_pattern('restock_orders:*')

def invalidate_tenant_cache(tenant_id):
    """Invalidate cache untuk tenant tertentu"""
    CacheService.invalidate_tenant_cache(tenant_id)
    CacheService.delete_pattern(f'restock_orders:*:tenant:{tenant_id}:*')

# --- Rute untuk Tenant ---
@bp.route('/')
@login_required
def index():
    """Halaman Marketplace untuk dilihat oleh Tenant dengan caching."""
    try:
        # Coba ambil dari cache terlebih dahulu
        cache_key = get_marketplace_cache_key()
        cached_data = CacheService.get_cache(cache_key)
        
        if cached_data:
            current_app.logger.info('Serving marketplace index from cache')
            items, payment_methods = cached_data
        else:
            # Jika tidak ada di cache, query dari database
            items = MarketplaceItem.query.filter(
                MarketplaceItem.stock > 0
            ).order_by(MarketplaceItem.created_at.desc()).all()
            
            payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
            
            # Cache hasil query
            cache_data = (items, payment_methods)
            CacheService.set_cache(cache_key, cache_data, 'medium')
            current_app.logger.info('Cached marketplace index data')
        
        return render_template('marketplace/index.html', 
                             items=items, 
                             payment_methods=payment_methods,
                             title="Marketplace")
                             
    except Exception as e:
        current_app.logger.error(f"Error in marketplace index: {str(e)}")
        # Fallback ke query database jika cache error
        items = MarketplaceItem.query.filter(MarketplaceItem.stock > 0).order_by(MarketplaceItem.created_at.desc()).all()
        payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
        return render_template('marketplace/index.html', 
                             items=items, 
                             payment_methods=payment_methods,
                             title="Marketplace")

@bp.route('/restock/<string:item_id>', methods=['GET', 'POST'])
@login_required
def restock_item(item_id):
    """Proses restock item dengan pembayaran dan verifikasi."""
    try:
        # Cache product details untuk performa yang lebih baik
        cache_key = ProductCacheService.get_product_cache_key(item_id, 'marketplace', 'details')
        item_to_restock = CacheService.get_or_set(
            cache_key,
            lambda: MarketplaceItem.query.get_or_404(item_id),
            'medium'
        )
        
        if not current_user.tenant_id:
            flash('Tenant tidak ditemukan untuk user ini.', 'danger')
            return redirect(url_for('marketplace.index'))
            
        tenant = Tenant.query.get(current_user.tenant_id)
        if not tenant:
            flash('Tenant tidak ditemukan.', 'danger')
            return redirect(url_for('marketplace.index'))
        
        form = RestockOrderForm()
        
        # Cache payment methods
        payment_methods_cache_key = get_payment_methods_cache_key()
        payment_methods = CacheService.get_or_set(
            payment_methods_cache_key,
            lambda: PaymentMethod.query.filter_by(is_active=True).all(),
            'long'
        )
        
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
                    destination_type=form.destination_type.data,
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
                
                # Invalidate cache terkait
                invalidate_tenant_cache(current_user.tenant_id)
                CacheService.delete_pattern(f'restock_orders:*:tenant:{current_user.tenant_id}:*')
                
                destination_message = "produk untuk dijual" if form.destination_type.data == 'product' else "bahan baku untuk produksi"
                flash(f'Order restock berhasil dibuat sebagai {destination_message}. Silakan tunggu verifikasi admin.', 'success')
                return redirect(url_for('marketplace.restock_orders'))
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating restock order: {str(e)}")
                flash(f'Error creating restock order: {str(e)}', 'danger')
        
        if form.errors:
            current_app.logger.warning(f"Form validation errors: {form.errors}")
        
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
    """Menampilkan riwayat restock orders tenant dengan caching."""
    try:
        status_filter = request.args.get('status')
        cache_key = get_restock_orders_cache_key(current_user.tenant_id, status_filter)
        
        orders = CacheService.get_or_set(
            cache_key,
            lambda: get_restock_orders_from_db(current_user.tenant_id, status_filter),
            'short'
        )
        
        return render_template('marketplace/restock_orders.html', 
                             orders=orders,
                             title="My Restock Orders")
    except Exception as e:
        current_app.logger.error(f"Error in restock_orders: {str(e)}")
        # Fallback ke database query
        orders = get_restock_orders_from_db(current_user.tenant_id, request.args.get('status'))
        return render_template('marketplace/restock_orders.html', 
                             orders=orders,
                             title="My Restock Orders")

def get_restock_orders_from_db(tenant_id, status_filter=None):
    """Helper function untuk mengambil restock orders dari database"""
    query = RestockOrder.query.filter_by(tenant_id=tenant_id)
    
    if status_filter:
        query = query.filter_by(status=RestockStatus(status_filter))
    
    return query.order_by(RestockOrder.created_at.desc()).all()

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
            
            # Invalidate cache tenant
            invalidate_tenant_cache(current_user.tenant_id)
            
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
    """Halaman detail untuk order tertentu dengan caching."""
    cache_key = CacheService.get_cache_key('order_detail', order_id)
    
    order = CacheService.get_or_set(
        cache_key,
        lambda: RestockOrder.query.filter_by(
            id=order_id, 
            tenant_id=current_user.tenant_id
        ).first_or_404(),
        'medium'
    )
    
    return render_template('marketplace/order_detail.html', 
                         order=order,
                         title=f"Order Details - {order.marketplace_item.name}")

# --- Rute untuk Superadmin ---

@bp.route('/manage')
@login_required
@superadmin_required
def manage():
    """Halaman Superadmin untuk mengelola semua item marketplace dengan caching."""
    try:
        filter_type = request.args.get('filter', 'all')
        cache_key = get_marketplace_cache_key(f"manage_{filter_type}")
        
        cached_data = CacheService.get_cache(cache_key)
        
        if cached_data:
            items, stats = cached_data
            current_app.logger.info('Serving marketplace manage from cache')
        else:
            items = get_marketplace_items_from_db(filter_type)
            stats = calculate_marketplace_stats(items)
            
            # Cache data
            cache_data = (items, stats)
            CacheService.set_cache(cache_key, cache_data, 'medium')
            current_app.logger.info('Cached marketplace manage data')
        
        total_items, in_stock_count, out_of_stock_count, total_value = stats
        
        return render_template('marketplace/manage.html', 
                             items=items,
                             total_items=total_items,
                             in_stock_count=in_stock_count,
                             out_of_stock_count=out_of_stock_count,
                             total_value="Rp{:,.2f}".format(total_value),
                             title="Manage Marketplace")
    except Exception as e:
        current_app.logger.error(f"Error in marketplace manage: {str(e)}")
        # Fallback ke database query
        items = get_marketplace_items_from_db(request.args.get('filter', 'all'))
        stats = calculate_marketplace_stats(items)
        total_items, in_stock_count, out_of_stock_count, total_value = stats
        
        return render_template('marketplace/manage.html', 
                             items=items,
                             total_items=total_items,
                             in_stock_count=in_stock_count,
                             out_of_stock_count=out_of_stock_count,
                             total_value="Rp{:,.2f}".format(total_value),
                             title="Manage Marketplace")

def get_marketplace_items_from_db(filter_type):
    """Helper function untuk mengambil marketplace items dari database"""
    query = MarketplaceItem.query
    
    if filter_type == 'in_stock':
        query = query.filter(MarketplaceItem.stock > 0)
    elif filter_type == 'out_of_stock':
        query = query.filter(MarketplaceItem.stock == 0)
    
    return query.order_by(MarketplaceItem.name).all()

def calculate_marketplace_stats(items):
    """Helper function untuk menghitung statistik marketplace"""
    total_items = len(items)
    in_stock_count = len([item for item in items if item.stock > 0])
    out_of_stock_count = len([item for item in items if item.stock == 0])
    total_value = sum(item.price * item.stock for item in items)
    
    return total_items, in_stock_count, out_of_stock_count, total_value

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
            
            if form.image.data:
                s3_service = S3Service()
                image_url = s3_service.upload_product_image(form.image.data, f"marketplace_{new_item.id}")
                new_item.image_url = image_url
            
            db.session.add(new_item)
            db.session.commit()
            
            # Invalidate cache marketplace
            invalidate_marketplace_cache()
            
            flash(f'Item "{new_item.name}" has been created.', 'success')
            return redirect(url_for('marketplace.manage'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating marketplace item: {str(e)}")
            flash(f'Error creating item: {str(e)}', 'danger')
    
    return render_template('marketplace/create_edit_item.html', 
                         form=form, 
                         title="Create Marketplace Item", 
                         legend="Tambah Barang Marketplace")

@bp.route('/manage/edit/<string:item_id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def edit_item(item_id):
    """Form untuk mengedit item marketplace yang ada."""
    item = MarketplaceItem.query.get_or_404(item_id)
    form = MarketplaceItemForm(obj=item)
    
    form._obj = item
    
    if form.validate_on_submit():
        try:
            item.name = form.name.data
            item.description = form.description.data
            item.price = form.price.data
            item.stock = form.stock.data
            item.sku = form.sku.data

            if form.image.data:
                s3_service = S3Service()
                image_url = s3_service.upload_product_image(form.image.data, f"marketplace_{item.id}")
                
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
            
            # Invalidate cache terkait
            invalidate_marketplace_cache()
            ProductCacheService.invalidate_product_cache(item_id, 'marketplace')
            
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
        if item.image_url:
            try:
                s3_service = S3Service()
                if 'amazonaws.com/' in item.image_url:
                    object_name = item.image_url.split('amazonaws.com/')[1]
                    s3_service.delete_file(object_name)
            except Exception as e:
                current_app.logger.warning(f"Could not delete image from S3: {str(e)}")
        
        db.session.delete(item)
        db.session.commit()
        
        # Invalidate cache terkait
        invalidate_marketplace_cache()
        ProductCacheService.invalidate_product_cache(item_id, 'marketplace')
        
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
    """Halaman admin untuk memverifikasi restock orders dengan caching."""
    try:
        status_filter = request.args.get('status', 'pending')
        cache_key = get_restock_orders_cache_key(status=status_filter)
        
        orders = CacheService.get_or_set(
            cache_key,
            lambda: get_admin_restock_orders_from_db(status_filter),
            'short'
        )
        
        return render_template('marketplace/admin_restock_orders.html', 
                             orders=orders,
                             status_filter=status_filter,
                             title="Manage Restock Orders")
    except Exception as e:
        current_app.logger.error(f"Error in admin_restock_orders: {str(e)}")
        # Fallback ke database query
        orders = get_admin_restock_orders_from_db(request.args.get('status', 'pending'))
        return render_template('marketplace/admin_restock_orders.html', 
                             orders=orders,
                             status_filter=request.args.get('status', 'pending'),
                             title="Manage Restock Orders")

def get_admin_restock_orders_from_db(status_filter):
    """Helper function untuk mengambil admin restock orders dari database"""
    query = RestockOrder.query
    
    if status_filter == 'pending':
        query = query.filter_by(status=RestockStatus.PENDING)
    elif status_filter == 'verified':
        query = query.filter_by(status=RestockStatus.VERIFIED)
    elif status_filter == 'rejected':
        query = query.filter_by(status=RestockStatus.REJECTED)
    
    return query.order_by(RestockOrder.created_at.desc()).all()

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
            
            if new_status == RestockStatus.VERIFIED:
                if restock_order.destination_type == 'product':
                    existing_product = Product.query.filter_by(
                        tenant_id=restock_order.tenant_id, 
                        name=restock_order.marketplace_item.name
                    ).first()
                    
                    if existing_product:
                        existing_product.stock_quantity += restock_order.quantity
                        flash(f'Stok produk "{existing_product.name}" berhasil ditambahkan.', 'success')
                        current_app.logger.info(f"Updated product stock: {existing_product.name}, new stock: {existing_product.stock_quantity}")
                    else:
                        new_product = Product(
                            id=str(uuid.uuid4()),
                            name=restock_order.marketplace_item.name,
                            description=restock_order.marketplace_item.description,
                            price=restock_order.marketplace_item.price,
                            cost_price=restock_order.marketplace_item.price * 0.8,
                            stock_quantity=restock_order.quantity,
                            sku=restock_order.marketplace_item.sku or f"PROD-{uuid.uuid4().hex[:8]}",
                            tenant_id=restock_order.tenant_id,
                            image_url=restock_order.marketplace_item.image_url,
                            requires_stock_tracking=True
                        )
                        db.session.add(new_product)
                        flash(f'Produk baru "{new_product.name}" berhasil dibuat.', 'success')
                        current_app.logger.info(f"Created new product: {new_product.name}, stock: {new_product.stock_quantity}")
                
                elif restock_order.destination_type == 'raw_material':
                    current_app.logger.info(f"Processing raw material restock for tenant: {restock_order.tenant_id}, item: {restock_order.marketplace_item.name}")
                    
                    existing_raw_material = RawMaterial.query.filter_by(
                        tenant_id=restock_order.tenant_id,
                        name=restock_order.marketplace_item.name
                    ).first()
                    
                    if existing_raw_material:
                        old_stock = existing_raw_material.stock_quantity
                        existing_raw_material.stock_quantity += restock_order.quantity
                        existing_raw_material.cost_price = restock_order.marketplace_item.price
                        existing_raw_material.is_active = True
                        flash(f'Stok bahan baku "{existing_raw_material.name}" berhasil ditambahkan.', 'success')
                        current_app.logger.info(f"Updated raw material: {existing_raw_material.name}, stock: {old_stock} -> {existing_raw_material.stock_quantity}")
                    else:
                        new_raw_material = RawMaterial(
                            id=str(uuid.uuid4()),
                            name=restock_order.marketplace_item.name,
                            description=restock_order.marketplace_item.description,
                            sku=restock_order.marketplace_item.sku or f"RM-{uuid.uuid4().hex[:8]}",
                            unit='pcs',
                            cost_price=restock_order.marketplace_item.price,
                            stock_quantity=restock_order.quantity,
                            stock_alert=10,
                            tenant_id=restock_order.tenant_id,
                            is_active=True
                        )
                        db.session.add(new_raw_material)
                        flash(f'Bahan baku baru "{new_raw_material.name}" berhasil dibuat.', 'success')
                        current_app.logger.info(f"Created new raw material: {new_raw_material.name}, stock: {new_raw_material.stock_quantity}, tenant: {new_raw_material.tenant_id}")
                
                old_marketplace_stock = restock_order.marketplace_item.stock
                restock_order.marketplace_item.stock -= restock_order.quantity
                current_app.logger.info(f"Updated marketplace item stock: {old_marketplace_stock} -> {restock_order.marketplace_item.stock}")
                
                db.session.commit()
                
                # Invalidate cache terkait
                invalidate_marketplace_cache()
                invalidate_tenant_cache(restock_order.tenant_id)
                CacheService.delete_pattern(f'restock_orders:*')
                CacheService.delete_pattern(f'order_detail:{restock_order.id}*')
                
                status_message = "verified" if new_status == RestockStatus.VERIFIED else "rejected"
                flash(f'Restock order has been {status_message}.', 'success')
                return redirect(url_for('marketplace.admin_restock_orders'))
            
            else:
                db.session.commit()
                
                # Invalidate cache
                invalidate_tenant_cache(restock_order.tenant_id)
                CacheService.delete_pattern(f'restock_orders:*')
                CacheService.delete_pattern(f'order_detail:{restock_order.id}*')
                
                flash('Restock order has been rejected.', 'success')
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
    """Kelola payment methods dengan caching."""
    try:
        cache_key = CacheService.get_cache_key('all_payment_methods')
        methods = CacheService.get_or_set(
            cache_key,
            lambda: PaymentMethod.query.order_by(PaymentMethod.created_at.desc()).all(),
            'long'
        )
        
        return render_template('marketplace/payment_methods.html', 
                             methods=methods,
                             title="Payment Methods")
    except Exception as e:
        current_app.logger.error(f"Error in payment_methods: {str(e)}")
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
            
            if form.qr_code.data:
                s3_service = S3Service()
                qr_code_url = s3_service.upload_product_image(
                    form.qr_code.data, 
                    f"qr_code_{new_method.id}"
                )
                new_method.qr_code_url = qr_code_url
            
            db.session.add(new_method)
            db.session.commit()
            
            # Invalidate payment methods cache
            CacheService.delete_pattern('payment_methods*')
            CacheService.delete_pattern('all_payment_methods*')
            
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

            if form.qr_code.data:
                s3_service = S3Service()
                qr_code_url = s3_service.upload_product_image(
                    form.qr_code.data, 
                    f"qr_code_{method.id}"
                )
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
            
            # Invalidate payment methods cache
            CacheService.delete_pattern('payment_methods*')
            CacheService.delete_pattern('all_payment_methods*')
            
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
        
        # Invalidate payment methods cache
        CacheService.delete_pattern('payment_methods*')
        CacheService.delete_pattern('all_payment_methods*')
        
        flash('Payment method deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting payment method: {str(e)}")
        flash(f'Error deleting payment method: {str(e)}', 'danger')
    
    return redirect(url_for('marketplace.payment_methods'))

# --- API Endpoints untuk Cache Management ---
@bp.route('/api/cache/clear-marketplace', methods=['POST'])
@login_required
@superadmin_required
def clear_marketplace_cache():
    """API endpoint untuk membersihkan cache marketplace (superadmin only)"""
    try:
        invalidate_marketplace_cache()
        flash('Marketplace cache berhasil dibersihkan.', 'success')
        return jsonify({'success': True, 'message': 'Marketplace cache cleared'})
    except Exception as e:
        current_app.logger.error(f"Error clearing marketplace cache: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/cache/status')
@login_required
@superadmin_required
def cache_status():
    """API endpoint untuk mengecek status cache"""
    try:
        # Test cache connection
        test_key = 'cache_test'
        CacheService.set_cache(test_key, 'test_value', 'short')
        test_result = CacheService.get_cache(test_key)
        CacheService.delete_cache(test_key)
        
        return jsonify({
            'success': True,
            'cache_available': test_result == 'test_value',
            'message': 'Cache service is working properly'
        })
    except Exception as e:
        current_app.logger.error(f"Error checking cache status: {str(e)}")
        return jsonify({
            'success': False,
            'cache_available': False,
            'message': str(e)
        }), 500