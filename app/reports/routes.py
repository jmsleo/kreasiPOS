from flask import render_template, jsonify, request, send_file
from flask_login import login_required, current_user
from app.reports import bp
from app.models import Sale, Product, SaleItem, db
from datetime import datetime, timedelta
import io
import openpyxl
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4

@bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')

@bp.route('/sales-report')
@login_required
def sales_report():
    # Filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query
    query = Sale.query.filter_by(tenant_id=current_user.tenant_id)
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Sale.created_at >= start_date)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Sale.created_at < end_date)
    
    sales = query.order_by(Sale.created_at.desc()).all()
    
    # Summary statistics
    total_sales = len(sales)
    total_revenue = sum(sale.total_amount for sale in sales)
    avg_sale = total_revenue / total_sales if total_sales else 0
    
    return render_template('reports/sales_report.html', 
                         sales=sales,
                         total_sales=total_sales,
                         total_revenue=total_revenue,
                         avg_sale=avg_sale)

@bp.route('/export-excel')
@login_required
def export_excel():
    """Export sales report to Excel"""
    # Get sales data
    sales = Sale.query.filter_by(tenant_id=current_user.tenant_id)\
        .order_by(Sale.created_at.desc()).all()
    
    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"
    
    # Headers
    headers = ['Receipt No', 'Date', 'Customer', 'Items', 'Total Amount', 'Payment Method']
    ws.append(headers)
    
    # Data
    for sale in sales:
        items_count = sale.items.count()
        customer_name = sale.customer.name if sale.customer else 'Walk-in'
        
        ws.append([
            sale.receipt_number,
            sale.created_at.strftime('%Y-%m-%d %H:%M'),
            customer_name,
            items_count,
            sale.total_amount,
            sale.payment_method
        ])
    
    # Save to bytes buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@bp.route('/export-pdf')
@login_required
def export_pdf():
    """Export sales report to PDF"""
    sales = Sale.query.filter_by(tenant_id=current_user.tenant_id)\
        .order_by(Sale.created_at.desc()).limit(50).all()
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, f"Sales Report - {current_user.tenant.name}")
    p.setFont("Helvetica", 10)
    p.drawString(100, 780, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Table headers
    y_position = 750
    p.drawString(100, y_position, "Receipt No")
    p.drawString(200, y_position, "Date")
    p.drawString(300, y_position, "Total")
    p.drawString(400, y_position, "Payment")
    
    # Data rows
    y_position -= 20
    for sale in sales:
        if y_position < 100:  # New page jika perlu
            p.showPage()
            y_position = 750
        
        p.drawString(100, y_position, sale.receipt_number)
        p.drawString(200, y_position, sale.created_at.strftime('%m/%d %H:%M'))
        p.drawString(300, y_position, f"${sale.total_amount:.2f}")
        p.drawString(400, y_position, sale.payment_method)
        y_position -= 15
    
    p.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.pdf",
        mimetype='application/pdf'
    )

@bp.route('/dashboard-data')
@login_required
def dashboard_data():
    """API data untuk dashboard charts"""
    # Sales last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    daily_sales = db.session.query(
        db.func.date(Sale.created_at),
        db.func.sum(Sale.total_amount),
        db.func.count(Sale.id)
    ).filter(
        Sale.tenant_id == current_user.tenant_id,
        Sale.created_at >= start_date,
        Sale.created_at <= end_date
    ).group_by(db.func.date(Sale.created_at)).all()
    
    # Top products
    top_products = db.session.query(
        Product.name,
        db.func.sum(SaleItem.quantity),
        db.func.sum(SaleItem.total_price)
    ).join(SaleItem, Product.id == SaleItem.product_id)\
     .join(Sale, SaleItem.sale_id == Sale.id)\
     .filter(Sale.tenant_id == current_user.tenant_id)\
     .group_by(Product.id, Product.name)\
     .order_by(db.func.sum(SaleItem.total_price).desc())\
     .limit(10).all()
    
    return jsonify({
        'daily_sales': [
            {'date': str(date), 'revenue': float(revenue), 'count': count}
            for date, revenue, count in daily_sales
        ],
        'top_products': [
            {'name': name, 'quantity': int(quantity), 'revenue': float(revenue)}
            for name, quantity, revenue in top_products
        ]
    })