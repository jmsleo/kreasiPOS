from flask import render_template, jsonify, request, send_file
from flask_login import login_required, current_user
from app.reports import bp
from app.models import Sale, Product, SaleItem, db
from datetime import datetime, timedelta
import io
import openpyxl
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4

from app.utils.timezone import convert_utc_to_user_timezone

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

@bp.route('/sales/<sale_id>/details/html')
@login_required
def sale_details_html(sale_id):
    """Return sale details as HTML for modal - FIX untuk tombol View Details"""
    sale = Sale.query.filter_by(
        id=sale_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Convert timestamp to user timezone
    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at)
    
    return render_template('reports/sale_details_modal.html', sale=sale)

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
    """API data untuk dashboard charts dengan perhitungan yang benar"""
    today = datetime.now().date()
    
    # 1. Data untuk chart (7 hari terakhir)
    end_date = datetime.now()
    start_date_chart = end_date - timedelta(days=6)  # 7 hari termasuk hari ini
    
    daily_sales = db.session.query(
        db.func.date(Sale.created_at),
        db.func.sum(Sale.total_amount),
        db.func.count(Sale.id)
    ).filter(
        Sale.tenant_id == current_user.tenant_id,
        Sale.created_at >= start_date_chart,
        Sale.created_at <= end_date
    ).group_by(db.func.date(Sale.created_at)).all()
    
    # 2. Data statistik yang benar
    # Hari ini
    today_sales = db.session.query(
        db.func.sum(Sale.total_amount),
        db.func.count(Sale.id)
    ).filter(
        Sale.tenant_id == current_user.tenant_id,
        db.func.date(Sale.created_at) == today
    ).first()
    
    # Minggu ini (Senin - Minggu)
    start_of_week = today - timedelta(days=today.weekday())  # Senin
    end_of_week = start_of_week + timedelta(days=6)  # Minggu
    
    week_sales = db.session.query(
        db.func.sum(Sale.total_amount),
        db.func.count(Sale.id)
    ).filter(
        Sale.tenant_id == current_user.tenant_id,
        db.func.date(Sale.created_at) >= start_of_week,
        db.func.date(Sale.created_at) <= end_of_week
    ).first()
    
    # Bulan ini
    start_of_month = today.replace(day=1)
    end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    month_sales = db.session.query(
        db.func.sum(Sale.total_amount),
        db.func.count(Sale.id)
    ).filter(
        Sale.tenant_id == current_user.tenant_id,
        db.func.date(Sale.created_at) >= start_of_month,
        db.func.date(Sale.created_at) <= end_of_month
    ).first()
    
    # 3. Top products (30 hari terakhir untuk data yang lebih representatif)
    start_date_products = today - timedelta(days=30)
    
    top_products = db.session.query(
        Product.name,
        db.func.sum(SaleItem.quantity),
        db.func.sum(SaleItem.total_price)
    ).join(SaleItem, Product.id == SaleItem.product_id)\
     .join(Sale, SaleItem.sale_id == Sale.id)\
     .filter(
         Sale.tenant_id == current_user.tenant_id,
         Sale.created_at >= start_date_products
     ).group_by(Product.id, Product.name)\
     .order_by(db.func.sum(SaleItem.total_price).desc())\
     .limit(10).all()
    
    # Format response
    today_revenue, today_count = today_sales or (0, 0)
    week_revenue, week_count = week_sales or (0, 0)
    month_revenue, month_count = month_sales or (0, 0)
    
    # Rata-rata transaksi
    avg_sale_week = week_revenue / week_count if week_count > 0 else 0
    avg_sale_month = month_revenue / month_count if month_count > 0 else 0
    
    return jsonify({
        'daily_sales': [
            {'date': str(date), 'revenue': float(revenue or 0), 'count': count or 0}
            for date, revenue, count in daily_sales
        ],
        'top_products': [
            {'name': name, 'quantity': int(quantity or 0), 'revenue': float(revenue or 0)}
            for name, quantity, revenue in top_products
        ],
        'stats': {
            'today': {
                'revenue': float(today_revenue or 0),
                'count': today_count or 0
            },
            'week': {
                'revenue': float(week_revenue or 0),
                'count': week_count or 0
            },
            'month': {
                'revenue': float(month_revenue or 0),
                'count': month_count or 0
            },
            'avg_sale': float(avg_sale_week)  # Gunakan rata-rata minggu ini
        }
    })