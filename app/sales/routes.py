from flask import render_template, request, redirect, send_file, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from app.sales import bp
from app.sales.forms import SaleForm, CustomerSelectForm, RefundForm, RefundSearchForm, ProcessRefundForm, RefundReportForm
from app.models import Sale, SaleItem, Product, Customer, Refund, RefundItem, RefundStatus, db
from app.services.bom_service import BOMService
from app.services.inventory_service import InventoryService
from app.services.refund_service import RefundService
from app.middleware.tenant_middleware import tenant_required
from app.utils.timezone import get_user_timezone, convert_utc_to_user_timezone
from app.services.cache_service import (
    CacheService, 
    ProductCacheService, 
    DashboardCacheService,
    InventoryCacheService,
    ReportsCacheService
)
from app.services.enhanced_inventory_service import EnhancedInventoryService
from app.services.enhanced_bom_service import EnhancedBOMService
import uuid
from datetime import datetime, timedelta
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import mm
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128


@bp.route('/')
@login_required
@tenant_required
def index():
    """Sales index, redirects to POS"""
    return redirect(url_for('sales.pos'))


@bp.route('/history')
@login_required
@tenant_required
def history():
    """Sales history page dengan cache optimization"""
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '')
    payment_filter = request.args.get('payment_method', '')
    
    # Build cache key berdasarkan parameter filter
    cache_key = CacheService.get_cache_key(
        'sales_history', 
        page, 
        date_filter, 
        payment_filter, 
        tenant_id=current_user.tenant_id
    )
    
    # Gunakan cache dengan timeout short karena data sales sering berubah
    sales_data = CacheService.get_or_set(
        cache_key,
        lambda: _get_sales_history_data(current_user.tenant_id, page, date_filter, payment_filter),
        timeout='short'
    )
    
    return render_template('sales/history.html', 
                         sales=sales_data['sales'], 
                         date_filter=date_filter, 
                         payment_filter=payment_filter)


def _get_sales_history_data(tenant_id, page, date_filter, payment_filter):
    """Helper function untuk mendapatkan sales history data"""
    query = Sale.query.filter_by(tenant_id=tenant_id)

    if date_filter:
        query = query.filter(db.func.date(Sale.created_at) == date_filter)
    if payment_filter:
        query = query.filter(Sale.payment_method == payment_filter)

    sales = query.order_by(Sale.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    # Convert timestamps to user timezone
    for sale in sales.items:
        sale.local_created_at = convert_utc_to_user_timezone(sale.created_at)
    
    return {'sales': sales}


@bp.route('/pos')
@login_required
@tenant_required
def pos():
    """Point of Sale interface dengan cache optimization"""
    # Get products dengan cache - timeout short karena stock sering berubah
    products_cache_key = CacheService.get_cache_key(
        'pos_products', 
        tenant_id=current_user.tenant_id
    )
    
    products_data = CacheService.get_or_set(
        products_cache_key,
        lambda: _get_pos_products_data(current_user.tenant_id),
        timeout='short'
    )
    
    # Get customers dengan cache - timeout medium karena jarang berubah
    customers_cache_key = CacheService.get_cache_key(
        'pos_customers', 
        tenant_id=current_user.tenant_id
    )
    
    customers = CacheService.get_or_set(
        customers_cache_key,
        lambda: Customer.query.filter_by(
            tenant_id=current_user.tenant_id
        ).order_by(Customer.name).limit(10).all(),
        timeout='medium'
    )
    
    return render_template('sales/pos.html', 
                         products=products_data, 
                         customers=customers)


def _get_pos_products_data(tenant_id):
    """Helper function untuk mendapatkan products data untuk POS"""
    products = Product.query.filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).order_by(Product.name).all()
    
    products_data = []
    for product in products:
        # Check BOM availability untuk setiap product
        bom_available = True
        bom_details = None
        
        if product.has_bom:
            try:
                # Gunakan enhanced BOM service dengan cache
                bom_validation = EnhancedBOMService.validate_bom_availability(
                    product.id, 1, tenant_id  # Check for quantity 1
                )
                bom_available = bom_validation.get('is_available', False)
                bom_details = bom_validation
            except Exception as e:
                current_app.logger.error(f"BOM validation error for product {product.id}: {str(e)}")
                bom_available = product.check_bom_availability()
        
        products_data.append({
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'stock_quantity': product.stock_quantity,
            'unit': product.unit,
            'sku': product.sku,
            'image_url': product.image_url,
            'requires_stock_tracking': product.requires_stock_tracking,
            'has_bom': product.has_bom,
            'is_active': product.is_active,
            'stock_alert': product.stock_alert,
            'category_name': product.category.name if product.category else '',
            'bom_available': bom_available,
            'bom_details': bom_details
        })
    
    return products_data


@bp.route('/process-sale', methods=['POST'])
@login_required
@tenant_required
def process_sale():
    """Process new sale dengan cache invalidation yang komprehensif"""
    try:
        data = request.get_json()
        current_app.logger.info(f'Received sale data: {data}')
        
        if not data or 'items' not in data or not data['items']:
            return jsonify({'error': 'No items in sale'}), 400

        # Validate payment
        payment_method = data.get('payment_method', 'cash')
        total_amount = float(data.get('total_amount', 0))
        amount_paid = float(data.get('amount_paid', total_amount))
        
        if payment_method == 'cash' and amount_paid < total_amount:
            return jsonify({'error': f'Insufficient payment. Required: {total_amount}, Paid: {amount_paid}'}), 400

        # Validate stock and BOM availability sebelum processing
        products_to_invalidate = set()
        
        for item_data in data['items']:
            product_id = item_data['product_id']
            product = Product.query.filter_by(
                id=product_id,
                tenant_id=current_user.tenant_id
            ).first()
            
            if not product:
                return jsonify({'error': f'Product not found: {product_id}'}), 400
            
            products_to_invalidate.add(product_id)
            
            # Check regular stock
            if product.requires_stock_tracking and not product.has_bom:
                if product.stock_quantity < int(item_data['quantity']):
                    return jsonify({
                        'error': f'Insufficient stock for {product.name}: need {item_data["quantity"]}, have {product.stock_quantity}'
                    }), 400
            
            # Check BOM availability menggunakan enhanced service
            if product.has_bom:
                bom_validation = EnhancedBOMService.validate_bom_availability(
                    product.id, 
                    item_data['quantity'], 
                    current_user.tenant_id
                )
                
                if not bom_validation.get('is_available', False):
                    error_msg = f'Insufficient BOM materials for {product.name}'
                    missing_items = bom_validation.get('missing_items', [])
                    if missing_items:
                        missing_names = [item['name'] for item in missing_items]
                        error_msg += f': {", ".join(missing_names)}'
                    return jsonify({'error': error_msg}), 400
        
        # Create sale record
        receipt_number = f"RC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        sale = Sale(
            tenant_id=current_user.tenant_id,
            receipt_number=receipt_number,
            total_amount=float(data.get('total_amount', 0)),
            tax_amount=float(data.get('tax_amount', 0)),
            discount_amount=float(data.get('discount_amount', 0)),
            payment_method=data.get('payment_method', 'cash'),
            customer_id=data.get('customer_id') if data.get('customer_id') else None,
            user_id=current_user.id,
            notes=data.get('notes', '')
        )
        
        db.session.add(sale)
        db.session.flush()  # Get sale ID
        
        # Create sale items dan process inventory deductions
        for item_data in data['items']:
            product = Product.query.filter_by(
                id=item_data['product_id'],
                tenant_id=current_user.tenant_id
            ).first()
            
            if not product:
                raise ValueError(f"Product not found: {item_data['product_id']}")
            
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=int(item_data['quantity']),
                unit_price=float(item_data['unit_price']),
                total_price=float(item_data['total_price'])
            )
            
            db.session.add(sale_item)
            
            # Process inventory deductions menggunakan EnhancedInventoryService
            quantity_sold = int(item_data['quantity'])
            
            if product.has_bom:
                current_app.logger.info(f'Processing BOM deduction for {product.name}, quantity: {quantity_sold}')
                
                # Process BOM production/deduction
                bom_result = EnhancedBOMService.process_bom_production(
                    product.id, quantity_sold, current_user.tenant_id
                )
                
                if not bom_result.get('success', False):
                    raise ValueError(f"Failed to process BOM deduction for {product.name}: {bom_result.get('error')}")
                
                current_app.logger.info(f'BOM deduction completed for {product.name}')
                
            elif product.requires_stock_tracking:
                # Update regular product stock
                success = EnhancedInventoryService.update_product_stock(
                    product.id, quantity_sold, current_user.tenant_id, 'subtract'
                )
                
                if not success:
                    raise ValueError(f"Failed to update stock for {product.name}")
        
        db.session.commit()
        
        # COMPREHENSIVE CACHE INVALIDATION setelah sale berhasil
        _invalidate_caches_after_sale(current_user.tenant_id, products_to_invalidate)
        
        current_app.logger.info(f'Sale processed successfully: {receipt_number}')
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'receipt_number': sale.receipt_number,
            'message': 'Sale processed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error processing sale: {str(e)}')
        return jsonify({'error': f'Failed to process sale: {str(e)}'}), 500


def _invalidate_caches_after_sale(tenant_id, product_ids):
    """Invalidate semua cache yang terkait setelah sale berhasil"""
    try:
        # Invalidate product-related caches
        for product_id in product_ids:
            ProductCacheService.invalidate_product_cache(product_id, tenant_id)
            CacheService.delete_pattern(f"*product_availability*{product_id}*")
            CacheService.delete_pattern(f"*bom_validation*{product_id}*")
        
        # Invalidate sales-related caches
        CacheService.invalidate_tenant_cache(tenant_id, 'sales_history')
        CacheService.invalidate_tenant_cache(tenant_id, 'pos_products')
        CacheService.delete_pattern(f"*recent_activity*{tenant_id}*")
        CacheService.delete_pattern(f"*top_products*{tenant_id}*")
        
        # Invalidate dashboard caches
        DashboardCacheService.invalidate_dashboard_cache(tenant_id)
        
        # Invalidate inventory caches
        InventoryCacheService.invalidate_inventory_cache(tenant_id)
        
        # Invalidate reports caches
        ReportsCacheService.invalidate_reports_cache(tenant_id)
        
        current_app.logger.info(f"Cache invalidated for tenant {tenant_id} after sale")
        
    except Exception as e:
        current_app.logger.error(f"Error during cache invalidation: {str(e)}")


@bp.route('/create', methods=['POST'])
@login_required
@tenant_required
def create_sale():
    """Legacy route - redirects to process_sale"""
    return process_sale()


@bp.route('/<sale_id>/details/html')
@login_required
@tenant_required
def sale_details_html(sale_id):
    """Return sale details as HTML untuk modal"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Convert timestamp to user timezone
    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at)
    
    return render_template('sales/sale_details_modal.html', sale=sale)


@bp.route('/<sale_id>')
@login_required
@tenant_required
def view_sale(sale_id):
    """View sale details dengan cache"""
    cache_key = CacheService.get_cache_key(
        'sale_details', 
        sale_id, 
        tenant_id=current_user.tenant_id
    )
    
    sale_data = CacheService.get_or_set(
        cache_key,
        lambda: _get_sale_details_data(sale_id, current_user.tenant_id),
        timeout='medium'
    )
    
    return render_template('sales/view.html', sale=sale_data['sale'])


def _get_sale_details_data(sale_id, tenant_id):
    """Helper function untuk mendapatkan sale details"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=tenant_id
    ).first_or_404()
    
    # Convert timestamp to user timezone
    user_timezone = get_user_timezone()
    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at, user_timezone)
    
    return {'sale': sale}


@bp.route('/<sale_id>/receipt/data')
@login_required
@tenant_required
def receipt_data(sale_id):
    """API endpoint untuk mendapatkan receipt data untuk printing dengan cache"""
    cache_key = CacheService.get_cache_key(
        'receipt_data', 
        sale_id, 
        tenant_id=current_user.tenant_id
    )
    
    receipt_data = CacheService.get_or_set(
        cache_key,
        lambda: _get_receipt_data(sale_id, current_user.tenant_id),
        timeout='long'  # Receipt data tidak berubah
    )
    
    return jsonify(receipt_data)


def _get_receipt_data(sale_id, tenant_id):
    """Helper function untuk mendapatkan receipt data"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=tenant_id
    ).first_or_404()
    
    local_created_at = convert_utc_to_user_timezone(sale.created_at)
    
    # Prepare receipt data
    items_data = []
    for item in sale.items:
        items_data.append({
            'name': item.product.name,
            'quantity': item.quantity,
            'unit_price': float(item.unit_price),
            'total_price': float(item.total_price)
        })
    
    receipt_data = {
        'store_name': current_user.tenant.name,
        'store_address': current_user.tenant.address or '',
        'store_phone': current_user.tenant.phone or '',
        'receipt_number': sale.receipt_number,
        'date': local_created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'cashier': sale.user.username,
        'items': items_data,
        'subtotal': float(sale.total_amount - sale.tax_amount + sale.discount_amount),
        'tax': float(sale.tax_amount),
        'discount': float(sale.discount_amount),
        'grand_total': float(sale.total_amount),
        'payment_method': sale.payment_method,
        'amount_paid': float(sale.total_amount),
        'change': 0.0,
        'customer_name': sale.customer.name if sale.customer else 'Walk-in Customer'
    }
    
    return receipt_data


@bp.route('/<sale_id>/receipt')
@login_required
@tenant_required
def receipt(sale_id):
    """Generate receipt untuk sale"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Convert timestamp to user timezone
    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at)
    
    return render_template('sales/receipt.html', sale=sale)


@bp.route('/api/validate_cart', methods=['POST'])
@login_required
@tenant_required
def api_validate_cart():
    """API endpoint untuk validate cart items sebelum checkout dengan cache"""
    try:
        data = request.get_json()
        
        if not data or 'items' not in data:
            return jsonify({'error': 'No items provided'}), 400
        
        # Generate cache key berdasarkan cart contents
        cart_hash = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
        cache_key = CacheService.get_cache_key(
            'cart_validation', 
            cart_hash, 
            tenant_id=current_user.tenant_id
        )
        
        validation_result = CacheService.get_or_set(
            cache_key,
            lambda: _validate_cart_items(data, current_user.tenant_id),
            timeout='short'  # Short timeout karena cart bisa berubah cepat
        )
        
        return jsonify(validation_result)
        
    except Exception as e:
        current_app.logger.error(f'Error validating cart: {str(e)}')
        return jsonify({'error': str(e)}), 500


def _validate_cart_items(data, tenant_id):
    """Helper function untuk validate cart items"""
    # Validate availability menggunakan InventoryService
    is_valid, errors = InventoryService.validate_sale_availability(
        data['items'], 
        tenant_id
    )
    
    validation_details = []
    products_to_check = []
    
    for item_data in data['items']:
        product = Product.query.filter_by(
            id=item_data['product_id'],
            tenant_id=tenant_id
        ).first()
        
        if product:
            item_validation = {
                'product_id': product.id,
                'product_name': product.name,
                'requested_quantity': item_data['quantity'],
                'stock_available': product.stock_quantity if product.requires_stock_tracking else 'unlimited',
                'requires_stock_tracking': product.requires_stock_tracking,
                'has_bom': product.has_bom,
                'bom_available': True
            }
            
            # Check BOM availability jika applicable menggunakan cached service
            if product.has_bom:
                bom_validation = EnhancedBOMService.validate_bom_availability(
                    product.id, item_data['quantity'], tenant_id
                )
                item_validation['bom_available'] = bom_validation.get('is_available', False)
                item_validation['bom_details'] = bom_validation
            
            validation_details.append(item_validation)
            products_to_check.append(product.id)
    
    return {
        'valid': is_valid,
        'errors': errors,
        'details': validation_details
    }


@bp.route('/api/product_availability/<product_id>')
@login_required
@tenant_required
def api_product_availability(product_id):
    """API endpoint untuk check product availability dengan cache optimization"""
    try:
        quantity = request.args.get('quantity', 1, type=int)
        
        # Cache key untuk product availability
        cache_key = CacheService.get_cache_key(
            'product_availability', 
            product_id, 
            quantity, 
            tenant_id=current_user.tenant_id
        )
        
        availability = CacheService.get_or_set(
            cache_key,
            lambda: _get_product_availability_data(product_id, quantity, current_user.tenant_id),
            timeout='short'  # Short timeout karena stock sering berubah
        )
        
        return jsonify(availability)
        
    except Exception as e:
        current_app.logger.error(f'Error checking product availability: {str(e)}')
        return jsonify({'error': str(e)}), 500


def _get_product_availability_data(product_id, quantity, tenant_id):
    """Helper function untuk mendapatkan product availability data"""
    product = Product.query.filter_by(
        id=product_id,
        tenant_id=tenant_id
    ).first_or_404()
    
    availability = {
        'product_id': product.id,
        'product_name': product.name,
        'requires_stock_tracking': product.requires_stock_tracking,
        'stock_quantity': product.stock_quantity,
        'has_bom': product.has_bom,
        'available': True,
        'messages': []
    }
    
    # Check regular stock
    if product.requires_stock_tracking:
        if product.stock_quantity < quantity:
            availability['available'] = False
            availability['messages'].append(
                f'Insufficient stock: need {quantity}, have {product.stock_quantity}'
            )
    
    # Check BOM availability menggunakan enhanced service dengan cache
    if product.has_bom:
        bom_validation = EnhancedBOMService.validate_bom_availability(
            product_id, quantity, tenant_id
        )
        
        if not bom_validation.get('is_available', False):
            availability['available'] = False
            availability['messages'].append('Insufficient raw materials for BOM')
            availability['bom_details'] = bom_validation
    
    return availability


@bp.route('/api/products')
@login_required
@tenant_required
def api_products():
    """API endpoint untuk mendapatkan products untuk POS dengan cache"""
    try:
        # Gunakan cache yang sama dengan route POS
        products_cache_key = CacheService.get_cache_key(
            'pos_products', 
            tenant_id=current_user.tenant_id
        )
        
        products_data = CacheService.get_or_set(
            products_cache_key,
            lambda: _get_pos_products_data(current_user.tenant_id),
            timeout='short'
        )
        
        return jsonify(products_data)
        
    except Exception as e:
        current_app.logger.error(f'Error getting products: {str(e)}')
        return jsonify({'error': str(e)}), 500


@bp.route('/reports/daily')
@login_required
@tenant_required
def daily_report():
    """Daily sales report dengan cache optimization"""
    from datetime import date, timedelta
    from sqlalchemy import func
    
    # Get date range
    end_date = request.args.get('end_date', date.today().isoformat())
    start_date = request.args.get('start_date', (date.today() - timedelta(days=7)).isoformat())
    
    # Convert string dates to date objects
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Cache key untuk daily report
    cache_key = CacheService.get_cache_key(
        'daily_report', 
        start_date.isoformat(), 
        end_date.isoformat(), 
        tenant_id=current_user.tenant_id
    )
    
    report_data = CacheService.get_or_set(
        cache_key,
        lambda: _get_daily_report_data(current_user.tenant_id, start_date, end_date),
        timeout='medium'
    )
    
    return render_template('sales/daily_report.html',
                         daily_sales=report_data['daily_sales'],
                         top_products=report_data['top_products'],
                         start_date=start_date,
                         end_date=end_date)


def _get_daily_report_data(tenant_id, start_date, end_date):
    """Helper function untuk mendapatkan daily report data"""
    # Get daily sales data
    daily_sales = db.session.query(
        func.date(Sale.created_at).label('sale_date'),
        func.count(Sale.id).label('transaction_count'),
        func.sum(Sale.total_amount).label('total_amount')
    ).filter(
        Sale.tenant_id == tenant_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(func.date(Sale.created_at)).order_by('sale_date').all()
    
    # Get top products
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_sold'),
        func.sum(SaleItem.total_price).label('total_revenue')
    ).join(SaleItem).join(Sale).filter(
        Sale.tenant_id == tenant_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(Product.id, Product.name).order_by('total_revenue desc').limit(10).all()
    
    return {
        'daily_sales': daily_sales,
        'top_products': top_products
    }


# --- REFUND ROUTES dengan Cache Optimization ---

@bp.route('/refunds')
@login_required
@tenant_required
def refunds_index():
    """Refunds management index page dengan cache"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    # Cache key untuk refunds list
    cache_key = CacheService.get_cache_key(
        'refunds_list', 
        page, 
        status_filter, 
        tenant_id=current_user.tenant_id
    )
    
    refunds_data = CacheService.get_or_set(
        cache_key,
        lambda: _get_refunds_data(current_user.tenant_id, page, status_filter),
        timeout='short'
    )
    
    # Get refund statistics dengan cache
    stats_cache_key = CacheService.get_cache_key(
        'refund_stats', 
        tenant_id=current_user.tenant_id
    )
    
    stats = CacheService.get_or_set(
        stats_cache_key,
        lambda: RefundService.get_refund_statistics(current_user.tenant_id),
        timeout='medium'
    )
    
    return render_template('sales/refunds/index.html',
                         refunds=refunds_data['refunds'],
                         status_filter=status_filter,
                         stats=stats)


def _get_refunds_data(tenant_id, page, status_filter):
    """Helper function untuk mendapatkan refunds data"""
    status_enum = None
    if status_filter:
        try:
            status_enum = RefundStatus(status_filter)
        except ValueError:
            status_enum = None
    
    refunds = RefundService.get_refunds_by_tenant(
        tenant_id=tenant_id,
        status=status_enum,
        page=page,
        per_page=20
    )
    
    # Convert timestamps to user timezone
    if refunds and refunds.items:
        for refund in refunds.items:
            refund.local_created_at = convert_utc_to_user_timezone(refund.created_at)
            if refund.processed_at:
                refund.local_processed_at = convert_utc_to_user_timezone(refund.processed_at)
    
    return {'refunds': refunds}


@bp.route('/refunds/search', methods=['GET', 'POST'])
@login_required
@tenant_required
def search_refundable_sales():
    """Search untuk refundable sales dengan cache optimization"""
    form = RefundSearchForm()
    sales = None
    
    if form.validate_on_submit():
        search_type = form.search_type.data
        search_value = form.search_value.data
        days_limit = int(form.days_limit.data)
        
        # Cache key untuk search results
        cache_key = CacheService.get_cache_key(
            'refundable_sales_search',
            search_type,
            search_value,
            days_limit,
            tenant_id=current_user.tenant_id
        )
        
        try:
            sales = CacheService.get_or_set(
                cache_key,
                lambda: _search_refundable_sales_data(
                    current_user.tenant_id, search_type, search_value, days_limit
                ),
                timeout='short'
            )
            
            if not sales:
                flash('Tidak ditemukan transaksi yang dapat direfund dengan kriteria tersebut.', 'info')
                
        except Exception as e:
            current_app.logger.error(f'Error searching refundable sales: {str(e)}')
            flash('Terjadi kesalahan saat mencari transaksi.', 'danger')
            sales = []
    
    return render_template('sales/refunds/search.html', form=form, sales=sales)


def _search_refundable_sales_data(tenant_id, search_type, search_value, days_limit):
    """Helper function untuk mencari refundable sales"""
    if search_type == 'receipt_number':
        sale = Sale.query.filter(
            Sale.tenant_id == tenant_id,
            Sale.receipt_number.ilike(f'%{search_value}%'),
            Sale.payment_status == 'completed'
        ).first()
        
        if sale and sale.can_be_refunded():
            return [sale]
        else:
            return []
            
    elif search_type == 'customer_name':
        from app.models import Customer
        sales_query = Sale.query.join(Customer).filter(
            Sale.tenant_id == tenant_id,
            Customer.name.ilike(f'%{search_value}%'),
            Sale.payment_status == 'completed',
            Sale.created_at >= datetime.utcnow() - timedelta(days=days_limit)
        ).order_by(Sale.created_at.desc()).all()
        
        # Filter hanya refundable sales
        sales = [sale for sale in sales_query if sale.can_be_refunded()]
        
    elif search_type == 'date':
        try:
            search_date = datetime.strptime(search_value, '%Y-%m-%d').date()
            sales_query = Sale.query.filter(
                Sale.tenant_id == tenant_id,
                db.func.date(Sale.created_at) == search_date,
                Sale.payment_status == 'completed'
            ).order_by(Sale.created_at.desc()).all()
            
            # Filter hanya refundable sales
            sales = [sale for sale in sales_query if sale.can_be_refunded()]
            
        except ValueError:
            return []
    
    # Convert timestamps
    if sales:
        for sale in sales:
            sale.local_created_at = convert_utc_to_user_timezone(sale.created_at)
    
    return sales


@bp.route('/refunds/create/<sale_id>', methods=['GET', 'POST'])
@login_required
@tenant_required
def create_refund(sale_id):
    """Create a new refund untuk sale dengan cache invalidation"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    if not sale.can_be_refunded():
        flash('Transaksi ini tidak dapat direfund.', 'danger')
        return redirect(url_for('sales.refunds_index'))
    
    form = RefundForm()
    
    if form.validate_on_submit():
        try:
            # Get refund items dari form data
            refund_items_data = []
            
            for item in sale.items:
                refund_qty_key = f'refund_quantity_{item.id}'
                refund_qty = request.form.get(refund_qty_key, type=int)
                
                if refund_qty and refund_qty > 0:
                    # Validate refund quantity
                    if refund_qty > item.get_refundable_quantity():
                        flash(f'Jumlah refund untuk {item.product.name} melebihi yang tersedia.', 'danger')
                        return render_template('sales/refunds/create.html', form=form, sale=sale)
                    
                    refund_items_data.append({
                        'sale_item_id': item.id,
                        'quantity': refund_qty
                    })
            
            if not refund_items_data:
                flash('Pilih minimal satu item untuk direfund.', 'danger')
                return render_template('sales/refunds/create.html', form=form, sale=sale)
            
            # Validate refund request
            is_valid, error_message = RefundService.validate_refund_request(sale_id, refund_items_data)
            if not is_valid:
                flash(f'Validasi refund gagal: {error_message}', 'danger')
                return render_template('sales/refunds/create.html', form=form, sale=sale)
            
            # Create refund
            refund = RefundService.create_refund(
                sale_id=sale_id,
                refund_items=refund_items_data,
                refund_reason=form.refund_reason.data,
                notes=form.notes.data,
                user_id=current_user.id
            )
            
            # Invalidate refund-related caches
            CacheService.invalidate_tenant_cache(current_user.tenant_id, 'refunds_list')
            CacheService.invalidate_tenant_cache(current_user.tenant_id, 'refund_stats')
            
            flash(f'Refund berhasil dibuat dengan nomor: {refund.refund_number}', 'success')
            return redirect(url_for('sales.view_refund', refund_id=refund.id))
            
        except Exception as e:
            current_app.logger.error(f'Error creating refund: {str(e)}')
            flash(f'Gagal membuat refund: {str(e)}', 'danger')
    
    # Convert timestamp
    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at)
    
    return render_template('sales/refunds/create.html', form=form, sale=sale)


@bp.route('/refunds/<refund_id>')
@login_required
@tenant_required
def view_refund(refund_id):
    """View refund details dengan cache"""
    cache_key = CacheService.get_cache_key(
        'refund_details', 
        refund_id, 
        tenant_id=current_user.tenant_id
    )
    
    refund_data = CacheService.get_or_set(
        cache_key,
        lambda: _get_refund_details_data(refund_id, current_user.tenant_id),
        timeout='medium'
    )
    
    return render_template('sales/refunds/view.html', refund=refund_data['refund'])


def _get_refund_details_data(refund_id, tenant_id):
    """Helper function untuk mendapatkan refund details"""
    refund = Refund.query.filter_by(
        id=refund_id,
        tenant_id=tenant_id
    ).first_or_404()
    
    # Convert timestamps
    refund.local_created_at = convert_utc_to_user_timezone(refund.created_at)
    if refund.processed_at:
        refund.local_processed_at = convert_utc_to_user_timezone(refund.processed_at)
    
    return {'refund': refund}


@bp.route('/refunds/<refund_id>/process', methods=['GET', 'POST'])
@login_required
@tenant_required
def process_refund(refund_id):
    """Process a pending refund dengan cache invalidation"""
    refund = Refund.query.filter_by(
        id=refund_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    if refund.status != RefundStatus.PENDING:
        flash('Refund ini sudah diproses.', 'info')
        return redirect(url_for('sales.view_refund', refund_id=refund_id))
    
    form = ProcessRefundForm()
    form.refund_id.data = refund_id
    
    if form.validate_on_submit():
        try:
            action = form.action.data
            
            if action == 'process':
                processed_refund = RefundService.process_refund(
                    refund_id=refund_id,
                    user_id=current_user.id
                )
                
                # Invalidate caches setelah refund diproses
                _invalidate_caches_after_refund(current_user.tenant_id, refund_id)
                
                flash(f'Refund {processed_refund.refund_number} berhasil diproses.', 'success')
                
            elif action == 'cancel':
                cancelled_refund = RefundService.cancel_refund(
                    refund_id=refund_id,
                    user_id=current_user.id
                )
                
                # Invalidate caches setelah refund dibatalkan
                _invalidate_caches_after_refund(current_user.tenant_id, refund_id)
                
                flash(f'Refund {cancelled_refund.refund_number} dibatalkan.', 'info')
            
            return redirect(url_for('sales.view_refund', refund_id=refund_id))
            
        except Exception as e:
            current_app.logger.error(f'Error processing refund: {str(e)}')
            flash(f'Gagal memproses refund: {str(e)}', 'danger')
    
    # Convert timestamp
    refund.local_created_at = convert_utc_to_user_timezone(refund.created_at)
    
    return render_template('sales/refunds/process.html', form=form, refund=refund)


def _invalidate_caches_after_refund(tenant_id, refund_id):
    """Invalidate caches setelah refund diproses"""
    try:
        # Invalidate refund-related caches
        CacheService.invalidate_tenant_cache(tenant_id, 'refunds_list')
        CacheService.invalidate_tenant_cache(tenant_id, 'refund_stats')
        CacheService.delete_pattern(f"*refund_details*{refund_id}*")
        
        # Invalidate sales and dashboard caches karena refund mempengaruhi laporan
        CacheService.invalidate_tenant_cache(tenant_id, 'sales_history')
        DashboardCacheService.invalidate_dashboard_cache(tenant_id)
        ReportsCacheService.invalidate_reports_cache(tenant_id)
        
        current_app.logger.info(f"Cache invalidated for tenant {tenant_id} after refund {refund_id}")
        
    except Exception as e:
        current_app.logger.error(f"Error during refund cache invalidation: {str(e)}")


# --- PDF Receipt Functions ---

@bp.route('/<sale_id>/receipt/download_pdf')
@login_required
@tenant_required
def download_receipt_pdf(sale_id):
    """Generate dan download PDF receipt"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Convert timestamp to user timezone
    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at)
    
    # Generate PDF content
    pdf_buffer = _generate_receipt_pdf_content(sale)
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"receipt_{sale.receipt_number}.pdf",
        mimetype='application/pdf'
    )


@bp.route('/<sale_id>/receipt/print', methods=['GET', 'POST'])
@login_required
@tenant_required
def print_receipt(sale_id):
    """API endpoint untuk trigger receipt reprint"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    try:
        # Simulasi print job - integrasikan dengan printer service yang sebenarnya
        current_app.logger.info(f"Reprint job triggered for receipt: {sale.receipt_number} by {current_user.username}")
        
        return jsonify({
            'success': True, 
            'message': f"Receipt {sale.receipt_number} sent to printer (simulation)."
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to trigger reprint for receipt {sale.id}: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f"Print failed: {str(e)}"
        }), 500


def _generate_receipt_pdf_content(sale: Sale) -> io.BytesIO:
    """Membuat konten PDF untuk struk menggunakan reportlab"""
    buffer = io.BytesIO()
    
    # Tentukan ukuran kertas struk (80mm width)
    receipt_width = 80 * mm
    receipt_height = 297 * mm 
    
    p = canvas.Canvas(buffer, pagesize=(receipt_width, receipt_height))
    
    # Tentukan titik awal
    x_margin = 5 * mm
    x_margin_right = receipt_width - x_margin
    y_pos = receipt_height - 10 * mm
    
    # Tentukan tinggi baris
    line_height_small = 3.5 * mm
    line_height_normal = 4.5 * mm
    line_height_large = 6 * mm
    
    # Helper untuk menggambar baris
    def draw_line(text, font, size, y_offset, align='left'):
        nonlocal y_pos
        y_pos -= y_offset
        p.setFont(font, size)
        if align == 'center':
            p.drawCentredString(receipt_width / 2, y_pos, text)
        elif align == 'right':
            p.drawRightString(x_margin_right, y_pos, text)
        else: # left
            p.drawString(x_margin, y_pos, text)
        return y_pos

    # Header Tenant
    tenant_name = sale.tenant.name
    tenant_address = sale.tenant.address or 'Store Address'
    tenant_phone = sale.tenant.phone or 'N/A'
    
    draw_line(tenant_name, 'Helvetica-Bold', 12, line_height_large, 'center')
    draw_line(tenant_address, 'Helvetica', 8, line_height_small, 'center')
    draw_line(f"Tel: {tenant_phone}", 'Helvetica', 8, line_height_small, 'center')
    
    y_pos -= 2 * mm
    p.line(x_margin, y_pos, x_margin_right, y_pos)
    
    # Info Struk
    draw_line(f"RECEIPT: {sale.receipt_number}", 'Helvetica-Bold', 9, line_height_normal, 'center')
    draw_line(sale.local_created_at.strftime('%Y-%m-%d %H:%M:%S'), 'Helvetica', 8, line_height_small, 'center')
    
    y_pos -= 3 * mm
    p.line(x_margin, y_pos, x_margin_right, y_pos)
    y_pos -= 2 * mm
    
    # Items header
    draw_line("ITEM", 'Helvetica-Bold', 8, line_height_small)
    draw_line("QTY  PRICE    TOTAL", 'Helvetica-Bold', 8, line_height_small, 'right')
    
    y_pos -= 2 * mm
    p.line(x_margin, y_pos, x_margin_right, y_pos)
    y_pos -= 1 * mm
    
    # Items
    for item in sale.items:
        # Product name (bisa dipotong jika terlalu panjang)
        product_name = item.product.name
        if len(product_name) > 20:
            product_name = product_name[:17] + "..."
        
        draw_line(product_name, 'Helvetica', 8, line_height_small)
        
        # Quantity and price
        item_line = f"{item.quantity}  Rp{item.unit_price:.0f}  Rp{item.total_price:.0f}"
        draw_line(item_line, 'Helvetica', 8, line_height_small, 'right')
        
        y_pos -= 1 * mm
    
    y_pos -= 2 * mm
    p.line(x_margin, y_pos, x_margin_right, y_pos)
    y_pos -= 2 * mm
    
    # Totals
    subtotal = sale.total_amount - sale.tax_amount + sale.discount_amount
    draw_line(f"Subtotal: Rp{subtotal:.0f}", 'Helvetica', 8, line_height_small, 'right')
    
    if sale.tax_amount > 0:
        draw_line(f"Tax: Rp{sale.tax_amount:.0f}", 'Helvetica', 8, line_height_small, 'right')
    
    if sale.discount_amount > 0:
        draw_line(f"Discount: -Rp{sale.discount_amount:.0f}", 'Helvetica', 8, line_height_small, 'right')
    
    draw_line(f"TOTAL: Rp{sale.total_amount:.0f}", 'Helvetica-Bold', 9, line_height_normal, 'right')
    
    y_pos -= 2 * mm
    p.line(x_margin, y_pos, x_margin_right, y_pos)
    y_pos -= 2 * mm
    
    # Payment info
    draw_line(f"Payment: {sale.payment_method.upper()}", 'Helvetica', 8, line_height_small)
    draw_line(f"Cashier: {sale.user.username}", 'Helvetica', 8, line_height_small)
    
    if sale.customer:
        draw_line(f"Customer: {sale.customer.name}", 'Helvetica', 8, line_height_small)
    
    y_pos -= 5 * mm
    
    # Footer
    draw_line("Thank you for your business!", 'Helvetica', 8, line_height_normal, 'center')
    draw_line("Please come again", 'Helvetica', 8, line_height_small, 'center')
    
    p.save()
    buffer.seek(0)
    return buffer


# Import tambahan yang diperlukan
import hashlib
import json