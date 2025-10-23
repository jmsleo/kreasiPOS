from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.products import bp
from app.products.forms import ProductForm, CategoryForm, ProductSearchForm
from app.models import BOMHeader, Product, Category, db
from app.services.bom_service import BOMService
from app.middleware.tenant_middleware import tenant_required
from app.services.s3_service import S3Service
from app.utils.timezone import get_user_timezone, convert_utc_to_user_timezone
from app.services.cache_service import ProductCacheService, CacheService, InventoryCacheService
from app.services.enhanced_inventory_service import EnhancedInventoryService
import uuid

try:
    from app.services.bom_service import BOMService
except ImportError:
    # Fallback jika BOMService belum diimplementasi
    class BOMService:
        @staticmethod
        def get_bom_by_product(product_id):
            return BOMHeader.query.filter_by(product_id=product_id, is_active=True).first()
        
        @staticmethod
        def delete_bom(bom_id):
            bom = BOMHeader.query.get(bom_id)
            if bom:
                db.session.delete(bom)
                db.session.commit()
        
        @staticmethod
        def validate_bom_availability(bom_id, quantity):
            # Implementasi sederhana
            bom = BOMHeader.query.get(bom_id)
            if not bom:
                return False, "BOM not found"
            
            for item in bom.items:
                required = item.quantity * quantity
                if item.raw_material.stock_quantity < required:
                    return False, f"Insufficient {item.raw_material.name}"
            return True, "All materials available"

@bp.route('/')
@login_required
@tenant_required
def index():
    """Products listing page dengan cache"""
    search_form = ProductSearchForm()
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', '')
    search = request.args.get('search', '')
    show_inactive = request.args.get('show_inactive', False, type=bool)
    
    # Build cache key berdasarkan parameter
    filters = {
        'page': page,
        'category_id': category_id,
        'search': search,
        'show_inactive': show_inactive
    }
    
    # Coba dapatkan dari cache
    cached_products = ProductCacheService.get_cached_product_list(current_user.tenant_id, filters)
    
    if cached_products is not None:
        products = cached_products
    else:
        # Build query
        query = Product.query.filter_by(tenant_id=current_user.tenant_id)
        
        if not show_inactive:
            query = query.filter_by(is_active=True)
        
        if category_id:
            query = query.filter_by(category_id=category_id)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Product.name.ilike(search_term),
                    Product.sku.ilike(search_term),
                    Product.barcode.ilike(search_term)
                )
            )
        
        products = query.order_by(Product.name).paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Cache hasil query
        ProductCacheService.cache_product_list(current_user.tenant_id, filters, products)
    
    # Get categories dengan cache
    categories_cache_key = CacheService.get_cache_key('categories', tenant_id=current_user.tenant_id)
    categories = CacheService.get_or_set(
        categories_cache_key,
        lambda: Category.query.filter_by(tenant_id=current_user.tenant_id).order_by(Category.name).all(),
        timeout='long'
    )
    
    # Get inventory alerts dengan cache
    inventory_status = EnhancedInventoryService.get_inventory_status(current_user.tenant_id)
    low_stock_alerts = EnhancedInventoryService.get_low_stock_alerts(current_user.tenant_id)
    
    # Filter alerts untuk products saja
    low_stock_products = [alert for alert in low_stock_alerts if alert['type'] == 'product' and alert['severity'] == 'warning']
    out_of_stock_products = [alert for alert in low_stock_alerts if alert['type'] == 'product' and alert['severity'] == 'critical']
    
    # Get BOM availability issues
    bom_issues_cache_key = CacheService.get_cache_key('bom_issues', tenant_id=current_user.tenant_id)
    bom_issues = CacheService.get_or_set(
        bom_issues_cache_key,
        lambda: _get_bom_issues(current_user.tenant_id),
        timeout='short'
    )
    
    return render_template('products/index.html',
                         products=products,
                         categories=categories,
                         search_form=search_form,
                         search=search,
                         category_id=category_id,
                         show_inactive=show_inactive,
                         low_stock_products=low_stock_products,
                         out_of_stock_products=out_of_stock_products,
                         bom_issues=bom_issues)

def _get_bom_issues(tenant_id):
    """Helper function untuk mendapatkan BOM issues"""
    bom_products = Product.query.filter_by(
        tenant_id=tenant_id,
        is_active=True,
        has_bom=True
    ).all()
    
    bom_issues = []
    for product in bom_products:
        if not product.check_bom_availability():
            bom_issues.append(product)
    
    return bom_issues

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@tenant_required
def create():
    """Create new product dengan cache invalidation"""
    form = ProductForm()

    # Populate category choices dengan cache
    categories_cache_key = CacheService.get_cache_key('categories', tenant_id=current_user.tenant_id)
    categories = CacheService.get_or_set(
        categories_cache_key,
        lambda: Category.query.filter_by(tenant_id=current_user.tenant_id).order_by(Category.name).all(),
        timeout='long'
    )
    form.category_id.choices = [('', 'Select Category')] + [(c.id, c.name) for c in categories]

    if form.validate_on_submit():
        try:
            # Generate SKU if not provided
            sku = form.sku.data
            if not sku:
                sku = f"PRD-{str(uuid.uuid4())[:8].upper()}"

            # Handle image upload
            image_url = None
            if form.image.data:
                s3_service = S3Service()
                image_url = s3_service.upload_product_image(form.image.data, f"product_{sku}")

            # Handle stock quantity properly
            stock_quantity = form.stock_quantity.data if form.requires_stock_tracking.data else 0
            stock_alert = form.stock_alert.data if form.requires_stock_tracking.data else 0

            if stock_quantity < 0:
                flash('Stock quantity cannot be negative.', 'danger')
                return render_template('products/create.html', form=form)

            product = Product(
                tenant_id=current_user.tenant_id,
                name=form.name.data,
                description=form.description.data,
                sku=sku,
                barcode=form.barcode.data,
                price=form.price.data,
                cost_price=form.cost_price.data,
                stock_quantity=stock_quantity,
                stock_alert=stock_alert,
                unit=form.unit.data,
                carton_quantity=form.carton_quantity.data,
                category_id=form.category_id.data if form.category_id.data else None,
                image_url=image_url,
                requires_stock_tracking=form.requires_stock_tracking.data,
                has_bom=form.has_bom.data,
                is_active=form.is_active.data
            )

            db.session.add(product)
            db.session.commit()

            # Invalidate relevant caches
            ProductCacheService.invalidate_product_cache(product.id, current_user.tenant_id)
            CacheService.invalidate_tenant_cache(current_user.tenant_id, 'product_list')
            CacheService.invalidate_tenant_cache(current_user.tenant_id, 'categories')
            InventoryCacheService.invalidate_inventory_cache(current_user.tenant_id)

            flash(f'Product "{product.name}" has been created successfully. Stock: {product.stock_quantity}', 'success')

            if form.has_bom.data:
                flash('Please configure the BOM (Bill of Materials) for this product.', 'info')
                return redirect(url_for('bom.create_bom', product_id=product.id))

            return redirect(url_for('products.index'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating product: {str(e)}', 'danger')
            current_app.logger.error(f'Error creating product: {str(e)}')

    return render_template('products/create.html', form=form)

@bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
@tenant_required
def edit(id):
    """Edit existing product dengan cache invalidation"""
    product = Product.query.filter_by(id=id, tenant_id=current_user.tenant_id).first_or_404()

    form = ProductForm(obj=product)

    # Populate category choices dengan cache
    categories_cache_key = CacheService.get_cache_key('categories', tenant_id=current_user.tenant_id)
    categories = CacheService.get_or_set(
        categories_cache_key,
        lambda: Category.query.filter_by(tenant_id=current_user.tenant_id).order_by(Category.name).all(),
        timeout='long'
    )
    form.category_id.choices = [('', 'Select Category')] + [(c.id, c.name) for c in categories]

    if form.validate_on_submit():
        try:
            # Check if BOM status is changing
            bom_status_changed = product.has_bom != form.has_bom.data

            product.name = form.name.data
            product.description = form.description.data
            product.sku = form.sku.data
            product.barcode = form.barcode.data
            product.price = form.price.data
            product.cost_price = form.cost_price.data
            product.unit = form.unit.data
            product.carton_quantity = form.carton_quantity.data
            product.category_id = form.category_id.data if form.category_id.data else None

            # Handle image upload
            if form.image.data:
                try:
                    s3_service = S3Service()
                    image_url = s3_service.upload_product_image(form.image.data, f"product_{product.sku}")
                    if image_url:
                        product.image_url = image_url
                except Exception as upload_error:
                    current_app.logger.error(f"Image upload failed: {str(upload_error)}")

            product.requires_stock_tracking = form.requires_stock_tracking.data
            product.has_bom = form.has_bom.data
            product.is_active = form.is_active.data

            # Update stock fields
            if form.requires_stock_tracking.data:
                if form.stock_quantity.data < 0:
                    flash('Stock quantity cannot be negative.', 'danger')
                    return render_template('products/edit.html', form=form, product=product)
                
                product.stock_quantity = form.stock_quantity.data
                product.stock_alert = form.stock_alert.data
            else:
                product.stock_quantity = 0
                product.stock_alert = 0

            # If BOM is disabled, clean up existing BOM
            if not form.has_bom.data and product.bom_headers.count() > 0:
                for bom in product.bom_headers:
                    db.session.delete(bom)
                flash('Existing BOM has been removed.', 'info')

            db.session.commit()

            # Invalidate relevant caches
            ProductCacheService.invalidate_product_cache(product.id, current_user.tenant_id)
            CacheService.invalidate_tenant_cache(current_user.tenant_id, 'product_list')
            CacheService.invalidate_tenant_cache(current_user.tenant_id, 'categories')
            InventoryCacheService.invalidate_inventory_cache(current_user.tenant_id)

            flash(f'Product "{product.name}" has been updated successfully. Stock: {product.stock_quantity}', 'success')

            if form.has_bom.data and bom_status_changed and product.bom_headers.count() == 0:
                flash('Please configure the BOM (Bill of Materials) for this product.', 'info')
                return redirect(url_for('bom.create_bom', product_id=product.id))

            return redirect(url_for('products.index'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')
            current_app.logger.error(f'Error updating product: {str(e)}')

    # Set nilai form untuk stock tracking
    if not product.requires_stock_tracking:
        form.stock_quantity.data = 0
        form.stock_alert.data = 0

    active_bom = None
    if product.has_bom:
        try:
            active_bom = BOMService.get_bom_by_product(product.id)
        except:
            active_bom = BOMHeader.query.filter_by(product_id=product.id, is_active=True).first()

    return render_template('products/edit.html', form=form, product=product, active_bom=active_bom)

@bp.route('/<id>/delete', methods=['POST'])
@login_required
@tenant_required
def delete(id):
    """Delete product dengan cache invalidation"""
    product = Product.query.filter_by(id=id, tenant_id=current_user.tenant_id).first_or_404()
    
    try:
        # Check if product has sales
        if product.sale_items.count() > 0:
            flash('Cannot delete product that has sales history.', 'danger')
            return redirect(url_for('products.index'))
        
        # Delete associated BOMs first
        if product.has_bom:
            for bom in product.bom_headers:
                BOMService.delete_bom(bom.id)
        
        product_name = product.name
        db.session.delete(product)
        db.session.commit()
        
        # Invalidate relevant caches
        ProductCacheService.invalidate_product_cache(product.id, current_user.tenant_id)
        CacheService.invalidate_tenant_cache(current_user.tenant_id, 'product_list')
        CacheService.invalidate_tenant_cache(current_user.tenant_id, 'categories')
        InventoryCacheService.invalidate_inventory_cache(current_user.tenant_id)
        
        flash(f'Product "{product_name}" has been deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'danger')
        current_app.logger.error(f'Error deleting product: {str(e)}')
    
    return redirect(url_for('products.index'))

@bp.route('/<id>/toggle_status', methods=['POST'])
@login_required
@tenant_required
def toggle_status(id):
    """Toggle product active status dengan cache invalidation"""
    product = Product.query.filter_by(id=id, tenant_id=current_user.tenant_id).first_or_404()
    
    try:
        product.is_active = not product.is_active
        db.session.commit()
        
        # Invalidate caches
        ProductCacheService.invalidate_product_cache(product.id, current_user.tenant_id)
        CacheService.invalidate_tenant_cache(current_user.tenant_id, 'product_list')
        InventoryCacheService.invalidate_inventory_cache(current_user.tenant_id)
        
        status = 'activated' if product.is_active else 'deactivated'
        flash(f'Product "{product.name}" has been {status}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating product status: {str(e)}', 'danger')
        current_app.logger.error(f'Error updating product status: {str(e)}')
    
    return redirect(url_for('products.index'))

@bp.route('/categories')
@login_required
@tenant_required
def categories():
    """Categories management page dengan cache"""
    categories_cache_key = CacheService.get_cache_key('categories', tenant_id=current_user.tenant_id)
    categories = CacheService.get_or_set(
        categories_cache_key,
        lambda: Category.query.filter_by(tenant_id=current_user.tenant_id).order_by(Category.name).all(),
        timeout='long'
    )
    form = CategoryForm()
    
    return render_template('products/categories.html', categories=categories, form=form)

@bp.route('/categories/create', methods=['GET', 'POST'])
@login_required
@tenant_required
def create_category():
    """Create new category dengan cache invalidation"""
    form = CategoryForm()
    
    if form.validate_on_submit():
        try:
            category = Category(
                tenant_id=current_user.tenant_id,
                name=form.name.data,
                description=form.description.data
            )
            
            db.session.add(category)
            db.session.commit()
            
            # Invalidate categories cache
            CacheService.invalidate_tenant_cache(current_user.tenant_id, 'categories')
            CacheService.invalidate_tenant_cache(current_user.tenant_id, 'product_list')
            
            flash(f'Category "{category.name}" has been created successfully.', 'success')
            return redirect(url_for('products.categories'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating category: {str(e)}', 'danger')
            current_app.logger.error(f'Error creating category: {str(e)}')
    
    return render_template('products/create_category.html', form=form)

@bp.route('/categories/<id>/update', methods=['POST'])
@login_required
@tenant_required
def update_category(id):
    """Update category dengan cache invalidation"""
    category = Category.query.filter_by(id=id, tenant_id=current_user.tenant_id).first_or_404()
    
    try:
        category.name = request.form.get('name')
        category.description = request.form.get('description')
        
        db.session.commit()
        
        # Invalidate categories cache
        CacheService.invalidate_tenant_cache(current_user.tenant_id, 'categories')
        CacheService.invalidate_tenant_cache(current_user.tenant_id, 'product_list')
        
        return jsonify({'success': True, 'message': f'Category "{category.name}" has been updated successfully.'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/categories/<id>/delete', methods=['POST'])
@login_required
@tenant_required
def delete_category(id):
    """Delete category dengan cache invalidation"""
    category = Category.query.filter_by(id=id, tenant_id=current_user.tenant_id).first_or_404()
    
    try:
        # Check if category has products
        if category.products.count() > 0:
            flash('Cannot delete category that has products. Please move products to another category first.', 'danger')
            return redirect(url_for('products.categories'))
        
        category_name = category.name
        db.session.delete(category)
        db.session.commit()
        
        # Invalidate categories cache
        CacheService.invalidate_tenant_cache(current_user.tenant_id, 'categories')
        CacheService.invalidate_tenant_cache(current_user.tenant_id, 'product_list')
        
        flash(f'Category "{category_name}" has been deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting category: {str(e)}', 'danger')
        current_app.logger.error(f'Error deleting category: {str(e)}')
    
    return redirect(url_for('products.categories'))

@bp.route('/api/search')
@login_required
@tenant_required
def api_search():
    """API endpoint untuk product search dengan cache"""
    search = request.args.get('q', '')
    
    # Cache key untuk search
    cache_key = CacheService.get_cache_key('product_search', search, tenant_id=current_user.tenant_id)
    
    results = CacheService.get_or_set(
        cache_key,
        lambda: _perform_product_search(search, current_user.tenant_id),
        timeout='short'
    )
    
    return jsonify(results)

def _perform_product_search(search, tenant_id):
    """Helper function untuk melakukan product search"""
    products = Product.query.filter(
        Product.tenant_id == tenant_id,
        Product.is_active == True,
        db.or_(
            Product.name.ilike(f'%{search}%'),
            Product.sku.ilike(f'%{search}%'),
            Product.barcode.ilike(f'%{search}%')
        )
    ).limit(10).all()
    
    results = []
    for product in products:
        bom_available = True
        if product.has_bom:
            bom_available = product.check_bom_availability()
        
        results.append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'stock_quantity': product.stock_quantity,
            'requires_stock_tracking': product.requires_stock_tracking,
            'has_bom': product.has_bom,
            'bom_available': bom_available,
            'image_url': product.image_url,
            'sku': product.sku,
            'barcode': product.barcode
        })
    
    return results

@bp.route('/api/<product_id>')
@login_required
@tenant_required
def api_get_product(product_id):
    """API endpoint untuk mendapatkan detail product dengan cache"""
    # Coba dapatkan dari cache
    cached_product = ProductCacheService.get_cached_product_details(product_id, current_user.tenant_id)
    
    if cached_product:
        return jsonify(cached_product)
    
    # Jika tidak ada di cache, query database
    product = Product.query.filter_by(
        id=product_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    product_data = product.to_dict()
    
    # Cache hasilnya
    ProductCacheService.cache_product_details(product_id, current_user.tenant_id, product_data)
    
    return jsonify(product_data)

@bp.route('/api/<product_id>/bom_validation')
@login_required
@tenant_required
def api_bom_validation(product_id):
    """API endpoint untuk validasi BOM availability dengan cache"""
    product = Product.query.filter_by(
        id=product_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    if not product.has_bom:
        return jsonify({'valid': True, 'message': 'Product does not use BOM'})
    
    quantity = request.args.get('quantity', 1, type=int)
    
    # Cache key untuk BOM validation
    cache_key = CacheService.get_cache_key('bom_validation', product_id, quantity, tenant_id=current_user.tenant_id)
    
    validation_result = CacheService.get_or_set(
        cache_key,
        lambda: _perform_bom_validation(product_id, quantity),
        timeout='short'
    )
    
    return jsonify(validation_result)

def _perform_bom_validation(product_id, quantity):
    """Helper function untuk melakukan validasi BOM"""
    try:
        active_bom = BOMService.get_bom_by_product(product_id)
    except:
        active_bom = BOMHeader.query.filter_by(product_id=product_id, is_active=True).first()
    
    if not active_bom:
        return {'valid': False, 'message': 'No active BOM found'}
    
    try:
        is_valid, details = BOMService.validate_bom_availability(active_bom.id, quantity)
        return {'valid': is_valid, 'details': details}
    except:
        # Fallback validation
        product = Product.query.get(product_id)
        is_available = product.check_bom_availability(quantity)
        return {'valid': is_available, 'message': 'BOM availability checked'}