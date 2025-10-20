import os
from flask import current_app, redirect, render_template, jsonify, request, url_for
from flask_login import login_required, current_user
from app.dashboard import bp
from app.models import Sale, Product, SaleItem, Customer, db
from datetime import datetime, timedelta
from sqlalchemy import func, extract
from app.utils.timezone import get_user_timezone, now_local, local_to_utc, convert_utc_to_user_timezone

def check_banners_exist():
    """Check if any banner images exist in static/banners/"""
    banner_dir = os.path.join(current_app.root_path, 'static', 'banners')
    
    if not os.path.exists(banner_dir):
        return False
    
    banner_files = ['banner1.jpg', 'banner2.jpg', 'banner3.jpg']
    
    for banner in banner_files:
        banner_path = os.path.join(banner_dir, banner)
        if os.path.exists(banner_path):
            return True
    
    return False

@bp.route('/')
@login_required
def index():
    """Dashboard utama dengan statistik real-time"""
    if current_user.role == 'cashier':
        return redirect(url_for('sales.pos'))
    
    # Get current time in user's timezone
    local_now = now_local()
    today = local_now.date()
    
    # Convert to UTC for database query
    today_start_utc = local_to_utc(datetime.combine(today, datetime.min.time()))
    today_end_utc = local_to_utc(datetime.combine(today, datetime.max.time()))
    
    # Today's statistics
    today_sales = Sale.query.filter(
        Sale.tenant_id == current_user.tenant_id,
        Sale.created_at >= today_start_utc,
        Sale.created_at <= today_end_utc
    ).all()
    
    today_revenue = sum(sale.total_amount for sale in today_sales)
    today_transactions = len(today_sales)
    
    # Low stock products
    low_stock_products = Product.query.filter(
        Product.tenant_id == current_user.tenant_id,
        Product.stock_quantity <= Product.stock_alert,
        Product.is_active == True
    ).count()
    
    # Total products
    total_products = Product.query.filter_by(
        tenant_id=current_user.tenant_id,
        is_active=True
    ).count()
    
    # Recent sales for activity feed
    recent_sales = Sale.query.filter_by(
        tenant_id=current_user.tenant_id
    ).order_by(Sale.created_at.desc()).limit(5).all()
    
    banner_exists = check_banners_exist()
    
    return render_template('dashboard/index.html',
                         today_revenue=today_revenue,
                         today_transactions=today_transactions,
                         low_stock_products=low_stock_products,
                         total_products=total_products,
                         recent_sales=recent_sales,
                         banner_exists=banner_exists)

@bp.route('/sales-data')
@login_required
def sales_data():
    """API data untuk dashboard charts - manual timezone handling"""
    days = int(request.args.get('days', 7))
    
    # Get user's timezone
    user_tz = get_user_timezone()
    
    # Calculate date range in user's timezone
    local_now = now_local()
    end_date_local = local_now
    start_date_local = end_date_local - timedelta(days=days-1)  # -1 to include today
    
    # Convert to UTC for database query
    start_date_utc = local_to_utc(start_date_local.replace(hour=0, minute=0, second=0, microsecond=0))
    end_date_utc = local_to_utc(end_date_local.replace(hour=23, minute=59, second=59, microsecond=999999))
    
    # Get all sales in the period (UTC)
    sales = Sale.query.filter(
        Sale.tenant_id == current_user.tenant_id,
        Sale.created_at >= start_date_utc,
        Sale.created_at <= end_date_utc
    ).all()
    
    # Group sales by local date manually
    daily_data = {}
    for sale in sales:
        # Convert UTC to user's local time
        local_sale_time = convert_utc_to_user_timezone(sale.created_at)
        sale_date = local_sale_time.date()
        date_key = sale_date.isoformat()
        
        if date_key not in daily_data:
            daily_data[date_key] = {
                'date': sale_date,
                'revenue': 0.0,
                'transactions': 0
            }
        
        daily_data[date_key]['revenue'] += float(sale.total_amount)
        daily_data[date_key]['transactions'] += 1
    
    # Prepare chart data with all dates in range (including empty ones)
    dates = []
    revenues = []
    transactions = []
    
    # Generate all dates in the range
    for i in range(days):
        current_date = start_date_local.date() + timedelta(days=i)
        date_key = current_date.isoformat()
        
        # Get data for this date or use zeros
        data = daily_data.get(date_key, {
            'date': current_date,
            'revenue': 0.0,
            'transactions': 0
        })
        
        dates.append(current_date.strftime('%m/%d'))
        revenues.append(data['revenue'])
        transactions.append(data['transactions'])
    
    return jsonify({
        'dates': dates,
        'revenues': revenues,
        'transactions': transactions
    })

@bp.route('/top-products')
@login_required
def top_products():
    """API untuk produk terlaris"""
    limit = int(request.args.get('limit', 10))
    days = int(request.args.get('days', 30))
    
    # Use local time for date range
    local_now = now_local()
    start_date_local = local_now - timedelta(days=days)
    start_date_utc = local_to_utc(start_date_local.replace(hour=0, minute=0, second=0, microsecond=0))
    
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_sold'),
        func.sum(SaleItem.total_price).label('revenue')
    ).join(SaleItem, Product.id == SaleItem.product_id)\
     .join(Sale, SaleItem.sale_id == Sale.id)\
     .filter(
         Sale.tenant_id == current_user.tenant_id,
         Sale.created_at >= start_date_utc
     ).group_by(Product.id, Product.name)\
     .order_by(func.sum(SaleItem.quantity).desc())\
     .limit(limit).all()
    
    products_data = []
    for product in top_products:
        products_data.append({
            'name': product.name,
            'sold': int(product.total_sold) if product.total_sold else 0,
            'revenue': float(product.revenue) if product.revenue else 0.0
        })
    
    return jsonify(products_data)

@bp.route('/recent-activity')
@login_required
def recent_activity():
    """API untuk aktivitas terbaru"""
    recent_sales = Sale.query.filter_by(
        tenant_id=current_user.tenant_id
    ).order_by(Sale.created_at.desc()).limit(10).all()
    
    activity_data = []
    for sale in recent_sales:
        # Convert UTC time to user's local time
        local_time = convert_utc_to_user_timezone(sale.created_at)
        
        activity_data.append({
            'type': 'sale',
            'title': f'New Sale - {sale.receipt_number}',
            'description': f'Rp{sale.total_amount:.2f} • {sale.payment_method}',
            'time': local_time.strftime('%H:%M'),
            'date': local_time.strftime('%Y-%m-%d'),
            'datetime': local_time.isoformat(),
            'icon': 'bi-cart-check'
        })
    
    return jsonify(activity_data)