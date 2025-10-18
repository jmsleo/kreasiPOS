from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.bom import bp
from app.bom.forms import BOMForm, BOMValidationForm
from app.models import BOMItem, Product, BOMHeader, RawMaterial, db
from app.services.bom_service import BOMService
from app.middleware.tenant_middleware import tenant_required

@bp.route('/product/<product_id>')
@login_required
@tenant_required
def view_bom(product_id):
    """View ALL BOMs for a specific product"""
    product = Product.query.filter_by(
        id=product_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Get all BOMs for this product, ordered by active status and creation date
    boms = BOMHeader.query.filter_by(
        product_id=product_id
    ).order_by(
        BOMHeader.is_active.desc(), 
        BOMHeader.created_at.desc()
    ).all()
    
    return render_template('bom/view.html', 
                         product=product, 
                         boms=boms)  # Changed from bom to boms

@bp.route('/product/<product_id>/create', methods=['GET', 'POST'])
@login_required
@tenant_required
def create_bom(product_id):
    """Create BOM for a product"""
    product = Product.query.filter_by(
        id=product_id,
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Get raw materials for dropdown
    raw_materials = RawMaterial.query.filter_by(
        tenant_id=current_user.tenant_id,
        is_active=True
    ).order_by(RawMaterial.name).all()
    
    form = BOMForm()
    
    # Populate raw material choices untuk semua item yang ada
    for item_form in form.items:
        item_form.raw_material_id.choices = [
            (rm.id, f"{rm.name} ({rm.unit})") for rm in raw_materials
        ]
    
    if request.method == 'POST':
        # PERBAIKAN: Baca SEMUA item dari form, tidak hanya index 0
        items_data = []
        i = 0
        
        # Loop sampai tidak ada item lagi
        while True:
            raw_material_id = request.form.get(f'items-{i}-raw_material_id')
            # Jika tidak ada raw_material_id untuk index ini, berhenti
            if not raw_material_id:
                break
                
            quantity = request.form.get(f'items-{i}-quantity')
            unit = request.form.get(f'items-{i}-unit')
            notes = request.form.get(f'items-{i}-notes')
            
            # Validasi: pastikan raw_material_id dan quantity ada
            if raw_material_id and raw_material_id != "" and quantity and float(quantity) > 0:
                try:
                    items_data.append({
                        'raw_material_id': raw_material_id,
                        'quantity': float(quantity),
                        'unit': unit or '',
                        'notes': notes or ''
                    })
                except ValueError:
                    flash('Jumlah harus berupa angka yang valid.', 'danger')
                    return render_template('bom/create.html', 
                                         form=form, 
                                         product=product, 
                                         raw_materials=raw_materials)
            i += 1
        
        # Debug: print untuk melihat data yang diterima
        current_app.logger.info(f"Received {len(items_data)} BOM items: {items_data}")
        
        if not items_data:
            flash('Minimal harus ada satu bahan baku dalam BOM.', 'danger')
            return render_template('bom/create.html', 
                                 form=form, 
                                 product=product, 
                                 raw_materials=raw_materials)
        
        try:
            # Buat BOM header
            bom = BOMHeader(
                product_id=product_id,
                notes=form.notes.data,
                is_active=True
            )
            db.session.add(bom)
            db.session.flush()  # Get the bom ID
            
            # Create BOM items dari SEMUA data yang dikumpulkan
            for item_data in items_data:
                bom_item = BOMItem(
                    bom_header_id=bom.id,
                    raw_material_id=item_data['raw_material_id'],
                    quantity=item_data['quantity'],
                    unit=item_data['unit'],
                    notes=item_data['notes']
                )
                db.session.add(bom_item)
                current_app.logger.info(f"Created BOM item: {item_data}")
            
            db.session.commit()
            
            flash(f'BOM baru untuk produk "{product.name}" berhasil dibuat dengan {len(items_data)} bahan baku.', 'success')
            return redirect(url_for('bom.view_bom', product_id=product_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error membuat BOM: {str(e)}', 'danger')
            current_app.logger.error(f'Error creating BOM: {str(e)}')
    
    return render_template('bom/create.html', 
                         form=form, 
                         product=product, 
                         raw_materials=raw_materials)

@bp.route('/<bom_id>/set_primary', methods=['POST'])
@login_required
@tenant_required
def set_primary_bom(bom_id):
    """Set a BOM as primary (deactivate others)"""
    bom = BOMHeader.query.filter_by(id=bom_id).first_or_404()
    
    # Check if BOM belongs to current tenant's product
    if bom.product.tenant_id != current_user.tenant_id:
        flash('BOM tidak ditemukan.', 'danger')
        return redirect(url_for('products.index'))
    
    try:
        # Deactivate all BOMs for this product
        BOMHeader.query.filter_by(
            product_id=bom.product_id
        ).update({'is_active': False})
        
        # Activate the selected BOM
        bom.is_active = True
        db.session.commit()
        
        flash(f'BOM telah ditetapkan sebagai BOM utama untuk produk "{bom.product.name}".', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error mengatur BOM utama: {str(e)}', 'danger')
        current_app.logger.error(f'Error setting primary BOM: {str(e)}')
    
    return redirect(url_for('bom.view_bom', product_id=bom.product_id))

@bp.route('/<bom_id>/edit', methods=['GET', 'POST'])
@login_required
@tenant_required
def edit_bom(bom_id):
    """Edit existing BOM"""
    bom = BOMHeader.query.filter_by(id=bom_id).first_or_404()
    
    # Check if BOM belongs to current tenant's product
    if bom.product.tenant_id != current_user.tenant_id:
        flash('BOM tidak ditemukan.', 'danger')
        return redirect(url_for('products.index'))
    
    # Get raw materials for dropdown
    raw_materials = RawMaterial.query.filter_by(
        tenant_id=current_user.tenant_id,
        is_active=True
    ).order_by(RawMaterial.name).all()
    
    form = BOMForm(obj=bom)
    
    if request.method == 'POST':
        # PERBAIKAN: Baca SEMUA item dari form
        items_data = []
        i = 0
        
        while True:
            raw_material_id = request.form.get(f'items-{i}-raw_material_id')
            if not raw_material_id:
                break
                
            quantity = request.form.get(f'items-{i}-quantity')
            unit = request.form.get(f'items-{i}-unit')
            notes = request.form.get(f'items-{i}-notes')
            
            if raw_material_id and raw_material_id != "" and quantity and float(quantity) > 0:
                try:
                    items_data.append({
                        'raw_material_id': raw_material_id,
                        'quantity': float(quantity),
                        'unit': unit or '',
                        'notes': notes or ''
                    })
                except ValueError:
                    flash('Jumlah harus berupa angka yang valid.', 'danger')
                    return render_template('bom/edit.html', 
                                         form=form, 
                                         bom=bom, 
                                         raw_materials=raw_materials)
            i += 1
        
        current_app.logger.info(f"Received {len(items_data)} BOM items for edit: {items_data}")
        
        if not items_data:
            flash('Minimal harus ada satu bahan baku dalam BOM.', 'danger')
            return render_template('bom/edit.html', 
                                 form=form, 
                                 bom=bom, 
                                 raw_materials=raw_materials)
        
        try:
            # Hapus item lama
            BOMItem.query.filter_by(bom_header_id=bom_id).delete()
            
            # Buat item baru dari SEMUA data
            for item_data in items_data:
                bom_item = BOMItem(
                    bom_header_id=bom_id,
                    raw_material_id=item_data['raw_material_id'],
                    quantity=item_data['quantity'],
                    unit=item_data['unit'],
                    notes=item_data['notes']
                )
                db.session.add(bom_item)
            
            # Update BOM header
            bom.notes = form.notes.data
            db.session.commit()
            
            flash(f'BOM untuk produk "{bom.product.name}" berhasil diupdate dengan {len(items_data)} bahan baku.', 'success')
            return redirect(url_for('bom.view_bom', product_id=bom.product_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error mengupdate BOM: {str(e)}', 'danger')
            current_app.logger.error(f'Error updating BOM: {str(e)}')
    
    return render_template('bom/edit.html', 
                         form=form, 
                         bom=bom, 
                         raw_materials=raw_materials)

@bp.route('/<bom_id>/delete', methods=['POST'])
@login_required
@tenant_required
def delete_bom(bom_id):
    """Delete BOM"""
    bom = BOMHeader.query.filter_by(id=bom_id).first_or_404()
    
    # Check if BOM belongs to current tenant's product
    if bom.product.tenant_id != current_user.tenant_id:
        flash('BOM tidak ditemukan.', 'danger')
        return redirect(url_for('products.index'))
    
    product_id = bom.product_id
    product_name = bom.product.name
    
    try:
        BOMService.delete_bom(bom_id)
        flash(f'BOM untuk produk "{product_name}" berhasil dihapus.', 'success')
    except Exception as e:
        flash(f'Error menghapus BOM: {str(e)}', 'danger')
        current_app.logger.error(f'Error deleting BOM: {str(e)}')
    
    return redirect(url_for('products.edit', id=product_id))

@bp.route('/api/validate', methods=['POST'])
@login_required
@tenant_required
def api_validate_bom():
    """API endpoint to validate BOM availability"""
    data = request.get_json()
    
    if not data or 'product_id' not in data:
        return jsonify({'error': 'Product ID required'}), 400
    
    product = Product.query.filter_by(
        id=data['product_id'],
        tenant_id=current_user.tenant_id
    ).first()
    
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    if not product.has_bom:
        return jsonify({'error': 'Product does not have BOM'}), 400
    
    active_bom = BOMService.get_bom_by_product(product.id)
    if not active_bom:
        return jsonify({'error': 'No active BOM found'}), 404
    
    quantity = data.get('quantity', 1)
    
    try:
        is_valid, details = BOMService.validate_bom_availability(active_bom.id, quantity)
        return jsonify(details)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/cost_analysis')
@login_required
@tenant_required
def cost_analysis():
    """Show BOM cost analysis for all products"""
    analysis_data = BOMService.get_bom_cost_analysis(current_user.tenant_id)
    
    return render_template('bom/cost_analysis.html', 
                         analysis_data=analysis_data)

@bp.route('/api/calculate_cost', methods=['POST'])
@login_required
@tenant_required
def api_calculate_cost():
    """API endpoint to calculate BOM cost in real-time"""
    data = request.get_json()
    
    if not data or 'items' not in data:
        return jsonify({'error': 'BOM items required'}), 400
    
    try:
        total_cost = 0
        item_costs = []
        
        for item in data['items']:
            raw_material = RawMaterial.query.filter_by(
                id=item['raw_material_id'],
                tenant_id=current_user.tenant_id
            ).first()
            
            if raw_material and raw_material.cost_price:
                item_cost = float(item['quantity']) * raw_material.cost_price
                total_cost += item_cost
                
                item_costs.append({
                    'raw_material_id': raw_material.id,
                    'raw_material_name': raw_material.name,
                    'quantity': float(item['quantity']),
                    'cost_per_unit': raw_material.cost_price,
                    'total_cost': item_cost
                })
        
        return jsonify({
            'total_cost': total_cost,
            'item_costs': item_costs
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500