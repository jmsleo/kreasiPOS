from flask import redirect, render_template, jsonify, request, url_for
from flask_login import login_required, current_user
from app.dashboard import bp
from app.models import Sale, Product, SaleItem, Customer, db
from datetime import datetime, timedelta
from sqlalchemy import func, extract

@bp.route('/')
@login_required
def index():
    """Dashboard utama dengan statistik real-time"""
    if current_user.role == 'cashier':
        return redirect(url_for('sales.pos'))
    # Today's statistics
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    today_sales = Sale.query.filter(
        Sale.tenant_id == current_user.tenant_id,
        Sale.created_at >= today_start,
        Sale.created_at <= today_end
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
    
    return render_template('dashboard/index.html',
                         today_revenue=today_revenue,
                         today_transactions=today_transactions,
                         low_stock_products=low_stock_products,
                         total_products=total_products,
                         recent_sales=recent_sales)

@bp.route('/sales-data')
@login_required
def sales_data():
    """API data untuk dashboard charts"""
    days = int(request.args.get('days', 7))
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Daily sales data
    daily_sales = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.sum(Sale.total_amount).label('revenue'),
        func.count(Sale.id).label('transactions')
    ).filter(
        Sale.tenant_id == current_user.tenant_id,
        Sale.created_at >= start_date,
        Sale.created_at <= end_date
    ).group_by(func.date(Sale.created_at)).order_by('date').all()
    
    # Format data untuk charts
    dates = []
    revenues = []
    transactions = []
    
    # Fill in missing dates
    for i in range(days):
        current_date = (end_date - timedelta(days=days-1-i)).date()
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Find data for this date
        data = next((x for x in daily_sales if x.date == current_date), None)
        
        dates.append(current_date.strftime('%m/%d'))
        revenues.append(float(data.revenue) if data else 0)
        transactions.append(int(data.transactions) if data else 0)
    
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
    
    start_date = datetime.now() - timedelta(days=days)
    
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_sold'),
        func.sum(SaleItem.total_price).label('revenue')
    ).join(SaleItem, Product.id == SaleItem.product_id)\
     .join(Sale, SaleItem.sale_id == Sale.id)\
     .filter(
         Sale.tenant_id == current_user.tenant_id,
         Sale.created_at >= start_date
     ).group_by(Product.id, Product.name)\
     .order_by(func.sum(SaleItem.quantity).desc())\
     .limit(limit).all()
    
    products_data = []
    for product in top_products:
        products_data.append({
            'name': product.name,
            'sold': int(product.total_sold),
            'revenue': float(product.revenue)
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
        activity_data.append({
            'type': 'sale',
            'title': f'New Sale - {sale.receipt_number}',
            'description': f'${sale.total_amount:.2f} • {sale.payment_method}',
            'time': sale.created_at.strftime('%H:%M'),
            'icon': 'bi-cart-check'
        })
    
    return jsonify(activity_data)