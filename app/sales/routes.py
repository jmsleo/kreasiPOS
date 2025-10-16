from flask import render_template, jsonify, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from app.sales import bp
from app.models import Sale, SaleItem, Product, Customer, db
from app.sales.forms import SaleForm
from app.services.printer_service import PrinterService
import json
from datetime import datetime
import uuid
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect()
@bp.route('/')
@login_required
def index():
    """Halaman utama sales - redirect ke POS"""
    return redirect(url_for('sales.pos'))

@bp.route('/pos')
@login_required
def pos():
    products = Product.query.filter_by(
        tenant_id=current_user.tenant_id, 
        is_active=True
    ).order_by(Product.name).all()
    customers = Customer.query.filter_by(tenant_id=current_user.tenant_id).order_by(Customer.name).all()
    return render_template('sales/pos.html', products=products, customers=customers)

@bp.route('/api/products')
@login_required
def api_products():
    """API untuk pencarian produk real-time"""
    search = request.args.get('q', '')
    category = request.args.get('category', '')
    
    query = Product.query.filter_by(
        tenant_id=current_user.tenant_id,
        is_active=True
    )
    
    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search}%'),
                Product.sku.ilike(f'%{search}%'),
                Product.barcode.ilike(f'%{search}%')
            )
        )
    
    if category:
        query = query.filter_by(category_id=category)
    
    products = query.limit(50).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': float(p.price),
        'stock_quantity': p.stock_quantity,
        'image_url': p.image_url,
        'sku': p.sku,
        'barcode': p.barcode
    } for p in products])

@bp.route('/process-sale', methods=['POST'])
@login_required
@csrf.exempt
def process_sale():
    try:
        data = request.get_json()
        if not data or 'items' not in data or not data['items']:
            return jsonify({'success': False, 'error': 'No items in cart'}), 400
        
        data = request.get_json()
        print("Parsed JSON data:", data)
        
        # Validasi data
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'}), 400
        
        if 'items' not in data:
            return jsonify({'success': False, 'error': 'Missing items field'}), 400
            
        if len(data['items']) == 0:
            return jsonify({'success': False, 'error': 'No items in cart'}), 400
        
        # Validasi field yang diperlukan
        required_fields = ['total_amount', 'payment_method']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Generate receipt number
        receipt_number = f"RCP-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Create sale
        sale = Sale(
            receipt_number=receipt_number,
            total_amount=float(data['total_amount']),
            tax_amount=float(data.get('tax_amount', 0)),
            discount_amount=float(data.get('discount_amount', 0)),
            payment_method=data['payment_method'],
            customer_id=data.get('customer_id'),
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            notes=data.get('notes', '')
        )
        db.session.add(sale)
        db.session.flush()  # Get sale ID without committing
        
        # Create sale items dan update stock
        for item in data['items']:
            # Validasi item structure
            if 'product_id' not in item or 'quantity' not in item:
                db.session.rollback()
                return jsonify({'success': False, 'error': 'Invalid item structure'}), 400
                
            product = Product.query.filter_by(
                id=item['product_id'],
                tenant_id=current_user.tenant_id
            ).first()
            
            if not product:
                db.session.rollback()
                return jsonify({'success': False, 'error': f"Product {item['product_id']} not found"}), 404
            
            if product.stock_quantity < item['quantity']:
                db.session.rollback()
                return jsonify({'success': False, 'error': f"Insufficient stock for {product.name}. Available: {product.stock_quantity}, Requested: {item['quantity']}"}), 400
            
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                unit_price=float(item.get('unit_price', product.price)),
                total_price=float(item.get('total_price', item['quantity'] * product.price))
            )
            db.session.add(sale_item)
            
            # Update stock quantity
            product.stock_quantity -= item['quantity']
            product.updated_at = datetime.utcnow()
        
        db.session.commit()
        
       # PERUBAHAN: Siapkan data struk untuk dikirim ke frontend
        receipt_data = {
            'company_name': current_user.tenant.name if current_user.tenant else 'T-POS ENTERPRISE',
            'store_name': getattr(current_user.tenant, 'store_name', 'Main Store'),
            'store_address': getattr(current_user.tenant, 'address', ''),
            'store_phone': getattr(current_user.tenant, 'phone', ''),
            'receipt_number': sale.receipt_number,
            'date': sale.created_at.strftime('%Y-%m-%d %H:%M'),
            'cashier': current_user.username,
            'items': [
                {
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.unit_price),
                    'total': float(item.total_price)
                } for item in sale.items
            ],
            'subtotal': float(sale.total_amount - sale.tax_amount + sale.discount_amount),
            'tax': float(sale.tax_amount),
            'discount': float(sale.discount_amount),
            'grand_total': float(sale.total_amount),
            'payment_method': sale.payment_method.upper(),
            'amount_paid': float(data.get('amount_paid', sale.total_amount)),
            'change': float(data.get('change_amount', 0))
        }

        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'receipt_number': sale.receipt_number,
            'receipt_data': receipt_data  # Kirim data ini ke frontend
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error in process_sale: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '')
    payment_filter = request.args.get('payment_method', '')
    
    query = Sale.query.filter_by(tenant_id=current_user.tenant_id)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d')
            next_day = filter_date.replace(day=filter_date.day + 1)
            query = query.filter(Sale.created_at >= filter_date, Sale.created_at < next_day)
        except ValueError:
            pass
    
    if payment_filter:
        query = query.filter_by(payment_method=payment_filter)
    
    sales = query.order_by(Sale.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('sales/history.html', sales=sales, 
                         date_filter=date_filter, payment_filter=payment_filter)

@bp.route('/receipt/<sale_id>')
@login_required
def receipt(sale_id):
    sale = Sale.query.filter_by(id=sale_id, tenant_id=current_user.tenant_id).first_or_404()
    return render_template('sales/receipt.html', sale=sale)

@bp.route('/receipt/<sale_id>/print')
@login_required
def print_receipt(sale_id):
    sale = Sale.query.filter_by(id=sale_id, tenant_id=current_user.tenant_id).first_or_404()
    
    try:
        printer_service = PrinterService()
        success = printer_service.print_receipt(sale, current_user.tenant)
        
        return jsonify({
            'success': success,
            'message': 'Receipt printed successfully' if success else 'Print failed'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/receipt/<sale_id>/pdf')
@login_required
def download_receipt_pdf(sale_id):
    """Download receipt sebagai PDF"""
    sale = Sale.query.filter_by(id=sale_id, tenant_id=current_user.tenant_id).first_or_404()
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    
    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, current_user.tenant.name)
    p.setFont("Helvetica", 10)
    p.drawString(100, 780, f"Receipt: {sale.receipt_number}")
    p.drawString(100, 765, f"Date: {sale.created_at.strftime('%Y-%m-%d %H:%M')}")
    p.drawString(100, 750, f"Cashier: {sale.user.username}")
    
    # Items
    y_position = 720
    p.drawString(100, y_position, "Item")
    p.drawString(300, y_position, "Qty")
    p.drawString(350, y_position, "Price")
    p.drawString(450, y_position, "Total")
    
    y_position -= 20
    for item in sale.items:
        p.drawString(100, y_position, item.product.name[:30])
        p.drawString(300, y_position, str(item.quantity))
        p.drawString(350, y_position, f"${item.unit_price:.2f}")
        p.drawString(450, y_position, f"${item.total_price:.2f}")
        y_position -= 15
        
        if y_position < 100:
            p.showPage()
            y_position = 800
    
    # Totals
    y_position -= 20
    p.drawString(350, y_position, "Subtotal:")
    p.drawString(450, y_position, f"${sale.total_amount - sale.tax_amount:.2f}")
    
    y_position -= 15
    p.drawString(350, y_position, "Tax:")
    p.drawString(450, y_position, f"${sale.tax_amount:.2f}")
    
    y_position -= 15
    p.drawString(350, y_position, "Total:")
    p.drawString(450, y_position, f"${sale.total_amount:.2f}")
    
    p.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"receipt_{sale.receipt_number}.pdf",
        mimetype='application/pdf'
    )