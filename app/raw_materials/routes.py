from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.raw_materials import bp
from app.raw_materials.forms import RawMaterialForm, RawMaterialSearchForm, StockUpdateForm
from app.models import RawMaterial, db
from app.services.raw_material_service import RawMaterialService
from app.middleware.tenant_middleware import tenant_required

@bp.route('/')
@login_required
@tenant_required
def index():
    """Raw materials listing page"""
    search_form = RawMaterialSearchForm()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    # PERBAIKAN: Handle include_inactive parameter dengan benar
    include_inactive = request.args.get('include_inactive', 'false', type=str).lower() == 'true'
    
    # PERBAIKAN: Set form data dengan benar
    search_form.search.data = search
    search_form.include_inactive.data = include_inactive
    
    # Get paginated raw materials
    raw_materials = RawMaterialService.get_raw_materials(
        tenant_id=current_user.tenant_id,
        include_inactive=include_inactive,  # Pastikan parameter ini benar
        search=search,
        page=page,
        per_page=20
    )
    
    # Get low stock alerts (hanya yang aktif)
    low_stock_materials = RawMaterialService.get_low_stock_materials(current_user.tenant_id)
    
    # Calculate total inventory value
    total_inventory_value = 0
    for material in raw_materials.items:
        material_value = (material.cost_price or 0) * (material.stock_quantity or 0)
        total_inventory_value += material_value
    
    return render_template('raw_materials/index.html',
                         raw_materials=raw_materials,
                         low_stock_materials=low_stock_materials,
                         search_form=search_form,
                         search=search,
                         include_inactive=include_inactive,
                         total_inventory_value=total_inventory_value)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@tenant_required
def create():
    """Create new raw material"""
    form = RawMaterialForm()
    
    # PERBAIKAN: Set default choices untuk unit
    form.unit.choices = [
        ('kg', 'Kilogram (kg)'),
        ('g', 'Gram (g)'),
        ('l', 'Liter (l)'),
        ('ml', 'Mililiter (ml)'),
        ('pcs', 'Pieces (pcs)'),
        ('m', 'Meter (m)'),
        ('cm', 'Centimeter (cm)'),
        ('box', 'Box'),
        ('pack', 'Pack')
    ]
    
    if form.validate_on_submit():
        try:
            # PERBAIKAN: Handle None values untuk cost_price
            cost_price = form.cost_price.data if form.cost_price.data else 0
            
            raw_material = RawMaterialService.create_raw_material(
                tenant_id=current_user.tenant_id,
                name=form.name.data,
                description=form.description.data,
                sku=form.sku.data,
                unit=form.unit.data,
                cost_price=cost_price,
                stock_quantity=form.stock_quantity.data,
                stock_alert=form.stock_alert.data,
                is_active=True  # PERBAIKAN: Default active
            )
            
            flash(f'Bahan baku "{raw_material.name}" berhasil dibuat.', 'success')
            return redirect(url_for('raw_materials.index'))
            
        except Exception as e:
            flash(f'Error membuat bahan baku: {str(e)}', 'danger')
            current_app.logger.error(f'Error creating raw material: {str(e)}')
    
    return render_template('raw_materials/create.html', form=form)

@bp.route('/<raw_material_id>/edit', methods=['GET', 'POST'])
@login_required
@tenant_required
def edit(raw_material_id):
    """Edit existing raw material"""
    raw_material = RawMaterial.query.filter_by(
        id=raw_material_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    form = RawMaterialForm(obj=raw_material)
    
    # PERBAIKAN: Set choices untuk unit
    form.unit.choices = [
        ('kg', 'Kilogram (kg)'),
        ('g', 'Gram (g)'),
        ('l', 'Liter (l)'),
        ('ml', 'Mililiter (ml)'),
        ('pcs', 'Pieces (pcs)'),
        ('m', 'Meter (m)'),
        ('cm', 'Centimeter (cm)'),
        ('box', 'Box'),
        ('pack', 'Pack')
    ]
    
    if form.validate_on_submit():
        try:
            # PERBAIKAN: Handle None values
            cost_price = form.cost_price.data if form.cost_price.data else 0
            
            updated_material = RawMaterialService.update_raw_material(
                raw_material_id=raw_material_id,
                name=form.name.data,
                description=form.description.data,
                sku=form.sku.data,
                unit=form.unit.data,
                cost_price=cost_price,
                stock_quantity=form.stock_quantity.data,
                stock_alert=form.stock_alert.data,
                is_active=form.is_active.data
            )
            
            flash(f'Bahan baku "{updated_material.name}" berhasil diupdate.', 'success')
            return redirect(url_for('raw_materials.index'))
            
        except Exception as e:
            flash(f'Error mengupdate bahan baku: {str(e)}', 'danger')
            current_app.logger.error(f'Error updating raw material: {str(e)}')
    
    return render_template('raw_materials/edit.html', form=form, raw_material=raw_material)

@bp.route('/<raw_material_id>/delete', methods=['POST'])
@login_required
@tenant_required
def delete(raw_material_id):
    """Delete raw material"""
    raw_material = RawMaterial.query.filter_by(
        id=raw_material_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    try:
        # PERBAIKAN: Cek apakah bahan baku digunakan di BOM sebelum hapus
        if raw_material.bom_items.count() > 0:
            flash(f'Tidak dapat menghapus "{raw_material.name}" karena masih digunakan dalam BOM.', 'danger')
            return redirect(url_for('raw_materials.index'))
            
        RawMaterialService.delete_raw_material(raw_material_id)
        flash(f'Bahan baku "{raw_material.name}" berhasil dihapus.', 'success')
        
    except Exception as e:
        flash(f'Error menghapus bahan baku: {str(e)}', 'danger')
        current_app.logger.error(f'Error deleting raw material: {str(e)}')
    
    return redirect(url_for('raw_materials.index'))

@bp.route('/<raw_material_id>/update_stock', methods=['POST'])
@login_required
@tenant_required
def update_stock(raw_material_id):
    """Update raw material stock"""
    raw_material = RawMaterial.query.filter_by(
        id=raw_material_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    form = StockUpdateForm()
    
    if form.validate_on_submit():
        try:
            # PERBAIKAN: Validasi untuk pengurangan stok
            if form.operation.data == 'subtract':
                current_stock = raw_material.stock_quantity or 0
                if current_stock < form.quantity.data:
                    flash(f'Stok tidak cukup. Stok saat ini: {current_stock} {raw_material.unit}', 'danger')
                    return redirect(url_for('raw_materials.index'))
            
            updated_material = RawMaterialService.update_stock(
                raw_material_id=raw_material_id,
                quantity=form.quantity.data,
                operation=form.operation.data
            )
            
            operation_text = 'ditambah' if form.operation.data == 'add' else 'dikurangi'
            flash(f'Stok {raw_material.name} berhasil {operation_text} sebanyak {form.quantity.data} {raw_material.unit}. Stok sekarang: {updated_material.stock_quantity}', 'success')
            
        except Exception as e:
            flash(f'Error mengupdate stok: {str(e)}', 'danger')
            current_app.logger.error(f'Error updating stock: {str(e)}')
    
    return redirect(url_for('raw_materials.index'))

@bp.route('/low_stock')
@login_required
@tenant_required
def low_stock():
    """Show raw materials with low stock"""
    low_stock_materials = RawMaterialService.get_low_stock_materials(current_user.tenant_id)
    
    # PERBAIKAN: Hitung total inventory value untuk low stock
    total_low_stock_value = 0
    for material in low_stock_materials:
        material_value = (material.cost_price or 0) * (material.stock_quantity or 0)
        total_low_stock_value += material_value
    
    return render_template('raw_materials/low_stock.html',
                         low_stock_materials=low_stock_materials,
                         total_low_stock_value=total_low_stock_value)

@bp.route('/usage_report')
@login_required
@tenant_required
def usage_report():
    """Show raw material usage report"""
    report_data = RawMaterialService.get_stock_usage_report(current_user.tenant_id)
    
    # PERBAIKAN: Hitung total inventory value yang akurat
    total_inventory_value = 0
    if report_data and 'materials' in report_data:
        for material in report_data['materials']:
            material_value = (material.cost_price or 0) * (material.stock_quantity or 0)
            total_inventory_value += material_value
    
    return render_template('raw_materials/usage_report.html',
                         report_data=report_data,
                         total_inventory_value=total_inventory_value)

@bp.route('/api/search')
@login_required
@tenant_required
def api_search():
    """API endpoint for raw material search (for BOM forms)"""
    search = request.args.get('q', '')
    
    raw_materials = RawMaterial.query.filter(
        RawMaterial.tenant_id == current_user.tenant_id,
        RawMaterial.is_active == True,
        RawMaterial.name.ilike(f'%{search}%')
    ).limit(10).all()
    
    results = []
    for material in raw_materials:
        results.append({
            'id': material.id,
            'name': material.name,
            'unit': material.unit,
            'cost_price': material.cost_price or 0,
            'stock_quantity': material.stock_quantity or 0,
            'is_low_stock': material.is_low_stock()  # PERBAIKAN: Tambah info low stock
        })
    
    return jsonify(results)

@bp.route('/api/<raw_material_id>')
@login_required
@tenant_required
def api_get_material(raw_material_id):
    """API endpoint to get raw material details"""
    raw_material = RawMaterial.query.filter_by(
        id=raw_material_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    return jsonify(raw_material.to_dict())

# Tambahkan routes berikut untuk fitur yang lebih lengkap

@bp.route('/<raw_material_id>/toggle_status', methods=['POST'])
@login_required
@tenant_required
def toggle_status(raw_material_id):
    """Toggle raw material active status"""
    raw_material = RawMaterial.query.filter_by(
        id=raw_material_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    try:
        raw_material.is_active = not raw_material.is_active
        db.session.commit()
        
        status = 'diaktifkan' if raw_material.is_active else 'dinonaktifkan'
        flash(f'Bahan baku "{raw_material.name}" berhasil {status}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error mengubah status bahan baku: {str(e)}', 'danger')
        current_app.logger.error(f'Error toggling raw material status: {str(e)}')
    
    return redirect(url_for('raw_materials.index'))

@bp.route('/export')
@login_required
@tenant_required
def export():
    """Export raw materials data"""
    import csv
    from io import StringIO
    from flask import Response
    
    try:
        raw_materials = RawMaterial.query.filter_by(
            tenant_id=current_user.tenant_id
        ).order_by(RawMaterial.name).all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Nama', 'SKU', 'Unit', 'Harga Cost', 'Stok', 'Minimal Stok', 'Status'])
        
        # Data
        for material in raw_materials:
            writer.writerow([
                material.name,
                material.sku or '',
                material.unit,
                material.cost_price or 0,
                material.stock_quantity or 0,
                material.stock_alert or 0,
                'Aktif' if material.is_active else 'Non-Aktif'
            ])
        
        output.seek(0)
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=bahan_baku.csv"}
        )
        
    except Exception as e:
        flash(f'Error mengekspor data: {str(e)}', 'danger')
        current_app.logger.error(f'Error exporting raw materials: {str(e)}')
        return redirect(url_for('raw_materials.index'))

@bp.route('/inventory_value')
@login_required
@tenant_required
def inventory_value():
    """Show total inventory value breakdown"""
    raw_materials = RawMaterial.query.filter_by(
        tenant_id=current_user.tenant_id,
        is_active=True
    ).order_by(RawMaterial.name).all()
    
    inventory_data = []
    total_value = 0
    
    for material in raw_materials:
        material_value = (material.cost_price or 0) * (material.stock_quantity or 0)
        total_value += material_value
        
        inventory_data.append({
            'material': material,
            'value': material_value,
            'percentage': 0  # Akan dihitung nanti
        })
    
    # Hitung persentase
    for item in inventory_data:
        if total_value > 0:
            item['percentage'] = (item['value'] / total_value) * 100
    
    return render_template('raw_materials/inventory_value.html',
                         inventory_data=inventory_data,
                         total_value=total_value)