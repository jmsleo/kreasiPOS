from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.sales import bp
from app.sales.forms import SaleForm, CustomerSelectForm
from app.models import Sale, SaleItem, Product, Customer, db
from app.services.inventory_service import InventoryService
from app.middleware.tenant_middleware import tenant_required
from app.utils.timezone import get_user_timezone, convert_utc_to_user_timezone
import uuid
from datetime import datetime

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
    """Sales history page"""
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '')
    payment_filter = request.args.get('payment_method', '')
    
    query = Sale.query.filter_by(tenant_id=current_user.tenant_id)

    if date_filter:
        query = query.filter(db.func.date(Sale.created_at) == date_filter)
    if payment_filter:
        query = query.filter(Sale.payment_method == payment_filter)

    sales = query.order_by(Sale.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    # Convert timestamps to user timezone
    user_timezone = get_user_timezone()
    for sale in sales.items:
        sale.local_created_at = convert_utc_to_user_timezone(sale.created_at, user_timezone)
    
    return render_template('sales/history.html', sales=sales, date_filter=date_filter, payment_filter=payment_filter)


@bp.route('/pos')
@login_required
@tenant_required
def pos():
    """Point of Sale interface"""
    # Get active products
    products = Product.query.filter_by(
        tenant_id=current_user.tenant_id,
        is_active=True
    ).order_by(Product.name).all()
    
    # Get customers for quick selection
    customers = Customer.query.filter_by(
        tenant_id=current_user.tenant_id
    ).order_by(Customer.name).limit(10).all()
    
    # Prepare products data for JSON
    products_data = []
    for product in products:
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
            'category_name': product.category.name if product.category else ''
        })
    
    return render_template('sales/pos.html', 
                         products=products_data, 
                         customers=customers)

@bp.route('/create', methods=['POST'])
@login_required
@tenant_required
def create_sale():
    """Process new sale - UPDATED for cash payment"""
    try:
        data = request.get_json()
        print('Received sale data:', data)  # Debug print
        
        if not data or 'items' not in data or not data['items']:
            return jsonify({'error': 'No items in sale'}), 400
        
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
        db.session.flush()  # Get the sale ID
        
        # Create sale items
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
            
            # Update product stock if tracking is enabled and no BOM
            if product.requires_stock_tracking and not product.has_bom:
                product.stock_quantity -= int(item_data['quantity'])
                if product.stock_quantity < 0:
                    product.stock_quantity = 0
        
        # Process BOM deductions
        for item_data in data['items']:
            product = Product.query.filter_by(
                id=item_data['product_id'],
                tenant_id=current_user.tenant_id
            ).first()
            
            if product and product.has_bom:
                product.process_bom_deduction(int(item_data['quantity']))
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'receipt_number': sale.receipt_number,
            'message': 'Sale processed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating sale: {str(e)}')
        return jsonify({'error': f'Failed to process sale: {str(e)}'}), 500

@bp.route('/<sale_id>')
@login_required
@tenant_required
def view_sale(sale_id):
    """View sale details"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Convert timestamp to user timezone
    user_timezone = get_user_timezone()
    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at, user_timezone)
    
    return render_template('sales/view.html', sale=sale)

@bp.route('/<sale_id>/receipt')
@login_required
@tenant_required
def receipt(sale_id):
    """Generate receipt for sale"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Convert timestamp to user timezone
    user_timezone = get_user_timezone()
    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at, user_timezone)
    
    return render_template('sales/receipt.html', sale=sale)

@bp.route('/api/validate_cart', methods=['POST'])
@login_required
@tenant_required
def api_validate_cart():
    """API endpoint to validate cart items before checkout"""
    try:
        data = request.get_json()
        
        if not data or 'items' not in data:
            return jsonify({'error': 'No items provided'}), 400
        
        # Validate availability
        is_valid, errors = InventoryService.validate_sale_availability(
            data['items'], 
            current_user.tenant_id
        )
        
        validation_details = []
        
        for item_data in data['items']:
            product = Product.query.filter_by(
                id=item_data['product_id'],
                tenant_id=current_user.tenant_id
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
                
                # Check BOM availability if applicable
                if product.has_bom:
                    item_validation['bom_available'] = product.check_bom_availability(item_data['quantity'])
                
                validation_details.append(item_validation)
        
        return jsonify({
            'valid': is_valid,
            'errors': errors,
            'details': validation_details
        })
        
    except Exception as e:
        current_app.logger.error(f'Error validating cart: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/api/product_availability/<product_id>')
@login_required
@tenant_required
def api_product_availability(product_id):
    """API endpoint to check product availability"""
    try:
        product = Product.query.filter_by(
            id=product_id,
            tenant_id=current_user.tenant_id
        ).first_or_404()
        
        quantity = request.args.get('quantity', 1, type=int)
        
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
                availability['messages'].append(f'Insufficient stock: need {quantity}, have {product.stock_quantity}')
        
        # Check BOM availability
        if product.has_bom:
            bom_available = product.check_bom_availability(quantity)
            if not bom_available:
                availability['available'] = False
                availability['messages'].append('Insufficient raw materials for BOM')
                
                # Get detailed BOM availability
                from app.services.bom_service import BOMService
                active_bom = BOMService.get_bom_by_product(product_id)
                if active_bom:
                    is_valid, details = BOMService.validate_bom_availability(active_bom.id, quantity)
                    availability['bom_details'] = details
        
        return jsonify(availability)
        
    except Exception as e:
        current_app.logger.error(f'Error checking product availability: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/reports/daily')
@login_required
@tenant_required
def daily_report():
    """Daily sales report"""
    from datetime import date, timedelta
    from sqlalchemy import func
    
    # Get date range
    end_date = request.args.get('end_date', date.today().isoformat())
    start_date = request.args.get('start_date', (date.today() - timedelta(days=7)).isoformat())
    
    # Convert string dates to date objects
    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get daily sales data
    daily_sales = db.session.query(
        func.date(Sale.created_at).label('sale_date'),
        func.count(Sale.id).label('transaction_count'),
        func.sum(Sale.total_amount).label('total_amount')
    ).filter(
        Sale.tenant_id == current_user.tenant_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(func.date(Sale.created_at)).order_by('sale_date').all()
    
    # Get top products
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_sold'),
        func.sum(SaleItem.total_price).label('total_revenue')
    ).join(SaleItem).join(Sale).filter(
        Sale.tenant_id == current_user.tenant_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(Product.id, Product.name).order_by('total_revenue desc').limit(10).all()
    
    return render_template('sales/daily_report.html',
                         daily_sales=daily_sales,
                         top_products=top_products,
                         start_date=start_date,
                         end_date=end_date)