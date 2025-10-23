from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.sales import bp
from app.sales.forms import RefundForm, RefundSearchForm, ProcessRefundForm, RefundReportForm
from app.models import Sale, SaleItem, Refund, RefundItem, RefundStatus, db
from app.services.refund_service import RefundService
from app.middleware.tenant_middleware import tenant_required
from app.utils.timezone import convert_utc_to_user_timezone
from datetime import datetime, timedelta
import json

@bp.route('/refunds')
@login_required
@tenant_required
def refunds_index():
    """Refunds management index page"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    # Get refunds with pagination
    status_enum = None
    if status_filter:
        try:
            status_enum = RefundStatus(status_filter)
        except ValueError:
            status_enum = None
    
    refunds = RefundService.get_refunds_by_tenant(
        tenant_id=current_user.tenant_id,
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
    
    # Get refund statistics
    stats = RefundService.get_refund_statistics(current_user.tenant_id)
    
    return render_template('sales/refunds/index.html',
                         refunds=refunds,
                         status_filter=status_filter,
                         stats=stats)

@bp.route('/refunds/search', methods=['GET', 'POST'])
@login_required
@tenant_required
def search_refundable_sales():
    """Search for refundable sales"""
    form = RefundSearchForm()
    sales = None
    
    if form.validate_on_submit():
        search_type = form.search_type.data
        search_value = form.search_value.data
        days_limit = int(form.days_limit.data)
        
        try:
            # Get refundable sales based on search criteria
            if search_type == 'receipt_number':
                sale = Sale.query.filter(
                    Sale.tenant_id == current_user.tenant_id,
                    Sale.receipt_number.ilike(f'%{search_value}%'),
                    Sale.payment_status == 'completed'
                ).first()
                
                if sale and sale.can_be_refunded():
                    sales = [sale]
                else:
                    sales = []
                    
            elif search_type == 'customer_name':
                from app.models import Customer
                sales_query = Sale.query.join(Customer).filter(
                    Sale.tenant_id == current_user.tenant_id,
                    Customer.name.ilike(f'%{search_value}%'),
                    Sale.payment_status == 'completed',
                    Sale.created_at >= datetime.utcnow() - timedelta(days=days_limit)
                ).order_by(Sale.created_at.desc()).all()
                
                # Filter only refundable sales
                sales = [sale for sale in sales_query if sale.can_be_refunded()]
                
            elif search_type == 'date':
                try:
                    search_date = datetime.strptime(search_value, '%Y-%m-%d').date()
                    sales_query = Sale.query.filter(
                        Sale.tenant_id == current_user.tenant_id,
                        db.func.date(Sale.created_at) == search_date,
                        Sale.payment_status == 'completed'
                    ).order_by(Sale.created_at.desc()).all()
                    
                    # Filter only refundable sales
                    sales = [sale for sale in sales_query if sale.can_be_refunded()]
                    
                except ValueError:
                    flash('Format tanggal tidak valid. Gunakan format YYYY-MM-DD', 'danger')
                    sales = []
            
            # Convert timestamps
            if sales:
                for sale in sales:
                    sale.local_created_at = convert_utc_to_user_timezone(sale.created_at)
            
            if not sales:
                flash('Tidak ditemukan transaksi yang dapat direfund dengan kriteria tersebut.', 'info')
                
        except Exception as e:
            current_app.logger.error(f'Error searching refundable sales: {str(e)}')
            flash('Terjadi kesalahan saat mencari transaksi.', 'danger')
            sales = []
    
    return render_template('sales/refunds/search.html', form=form, sales=sales)

@bp.route('/refunds/create/<sale_id>', methods=['GET', 'POST'])
@login_required
@tenant_required
def create_refund(sale_id):
    """Create a new refund for a sale"""
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
            # Get refund items from form data
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
    """View refund details"""
    refund = Refund.query.filter_by(
        id=refund_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Convert timestamps
    refund.local_created_at = convert_utc_to_user_timezone(refund.created_at)
    if refund.processed_at:
        refund.local_processed_at = convert_utc_to_user_timezone(refund.processed_at)
    
    return render_template('sales/refunds/view.html', refund=refund)

@bp.route('/refunds/<refund_id>/process', methods=['GET', 'POST'])
@login_required
@tenant_required
def process_refund(refund_id):
    """Process a pending refund"""
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
                flash(f'Refund {processed_refund.refund_number} berhasil diproses.', 'success')
                
            elif action == 'cancel':
                cancelled_refund = RefundService.cancel_refund(
                    refund_id=refund_id,
                    user_id=current_user.id
                )
                flash(f'Refund {cancelled_refund.refund_number} dibatalkan.', 'info')
            
            return redirect(url_for('sales.view_refund', refund_id=refund_id))
            
        except Exception as e:
            current_app.logger.error(f'Error processing refund: {str(e)}')
            flash(f'Gagal memproses refund: {str(e)}', 'danger')
    
    # Convert timestamp
    refund.local_created_at = convert_utc_to_user_timezone(refund.created_at)
    
    return render_template('sales/refunds/process.html', form=form, refund=refund)

@bp.route('/refunds/reports')
@login_required
@tenant_required
def refund_reports():
    """Refund reports page"""
    form = RefundReportForm()
    report_data = None
    
    # Set default dates (last 30 days)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    form.start_date.data = start_date.isoformat()
    form.end_date.data = end_date.isoformat()
    
    if request.method == 'POST' and form.validate_on_submit():
        try:
            start_date = datetime.strptime(form.start_date.data, '%Y-%m-%d')
            end_date = datetime.strptime(form.end_date.data, '%Y-%m-%d')
            
            # Get refund statistics for the period
            stats = RefundService.get_refund_statistics(
                tenant_id=current_user.tenant_id,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get detailed refunds for the period
            query = Refund.query.filter(
                Refund.tenant_id == current_user.tenant_id,
                Refund.created_at >= start_date,
                Refund.created_at <= end_date
            )
            
            if form.status_filter.data:
                query = query.filter(Refund.status == RefundStatus(form.status_filter.data))
            
            if form.reason_filter.data:
                query = query.filter(Refund.refund_reason == form.reason_filter.data)
            
            refunds = query.order_by(Refund.created_at.desc()).all()
            
            # Convert timestamps
            for refund in refunds:
                refund.local_created_at = convert_utc_to_user_timezone(refund.created_at)
                if refund.processed_at:
                    refund.local_processed_at = convert_utc_to_user_timezone(refund.processed_at)
            
            report_data = {
                'stats': stats,
                'refunds': refunds,
                'start_date': start_date,
                'end_date': end_date
            }
            
        except Exception as e:
            current_app.logger.error(f'Error generating refund report: {str(e)}')
            flash('Gagal membuat laporan refund.', 'danger')
    
    return render_template('sales/refunds/reports.html', form=form, report_data=report_data)

# API Endpoints
@bp.route('/api/refunds/validate', methods=['POST'])
@login_required
@tenant_required
def api_validate_refund():
    """API endpoint to validate refund request"""
    try:
        data = request.get_json()
        sale_id = data.get('sale_id')
        refund_items = data.get('refund_items', [])
        
        if not sale_id or not refund_items:
            return jsonify({'error': 'Missing sale_id or refund_items'}), 400
        
        is_valid, message = RefundService.validate_refund_request(sale_id, refund_items)
        
        return jsonify({
            'valid': is_valid,
            'message': message
        })
        
    except Exception as e:
        current_app.logger.error(f'Error validating refund: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/api/refunds/calculate', methods=['POST'])
@login_required
@tenant_required
def api_calculate_refund():
    """API endpoint to calculate refund amount"""
    try:
        data = request.get_json()
        refund_items = data.get('refund_items', [])
        
        total_refund_amount = 0.0
        item_details = []
        
        for item_data in refund_items:
            sale_item = SaleItem.query.get(item_data['sale_item_id'])
            if sale_item and sale_item.sale.tenant_id == current_user.tenant_id:
                refund_qty = int(item_data['quantity'])
                item_refund_amount = sale_item.unit_price * refund_qty
                total_refund_amount += item_refund_amount
                
                item_details.append({
                    'sale_item_id': sale_item.id,
                    'product_name': sale_item.product.name,
                    'quantity': refund_qty,
                    'unit_price': float(sale_item.unit_price),
                    'total_price': float(item_refund_amount)
                })
        
        return jsonify({
            'total_refund_amount': total_refund_amount,
            'item_details': item_details
        })
        
    except Exception as e:
        current_app.logger.error(f'Error calculating refund: {str(e)}')
        return jsonify({'error': str(e)}), 500