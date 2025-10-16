from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.products import bp
from app.products.forms import ProductForm, CategoryForm
from app.models import Product, Category, db
from app.services.s3_service import S3Service
import os

@bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    stock_status = request.args.get('stock_status', '')
    
    query = Product.query.filter_by(tenant_id=current_user.tenant_id)
    
    # Apply filters
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    
    if category_filter:
        query = query.filter_by(category_id=category_filter)
    
    if stock_status == 'low':
        query = query.filter(Product.stock_quantity <= Product.stock_alert)
    elif stock_status == 'out':
        query = query.filter(Product.stock_quantity == 0)
    elif stock_status == 'normal':
        query = query.filter(Product.stock_quantity > Product.stock_alert)
    
    products = query.order_by(Product.name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    categories = Category.query.filter_by(tenant_id=current_user.tenant_id).all()
    
    # Statistics
    total_products = Product.query.filter_by(tenant_id=current_user.tenant_id).count()
    active_products = Product.query.filter_by(tenant_id=current_user.tenant_id, is_active=True).count()
    low_stock_count = Product.query.filter(
        Product.tenant_id == current_user.tenant_id,
        Product.stock_quantity <= Product.stock_alert,
        Product.stock_quantity > 0
    ).count()
    out_of_stock_count = Product.query.filter_by(
        tenant_id=current_user.tenant_id, 
        stock_quantity=0
    ).count()
    
    return render_template('products/index.html',
                         products=products,
                         categories=categories,
                         total_products=total_products,
                         active_products=active_products,
                         low_stock_count=low_stock_count,
                         out_of_stock_count=out_of_stock_count)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = ProductForm()
    
    # Populate category choices
    form.category_id.choices = [('', 'Select Category')] + [
        (str(cat.id), cat.name) for cat in 
        Category.query.filter_by(tenant_id=current_user.tenant_id).all()
    ]
    
    if form.validate_on_submit():
        try:
            product = Product(
                name=form.name.data,
                description=form.description.data,
                sku=form.sku.data,
                barcode=form.barcode.data,
                price=form.price.data,
                cost_price=form.cost_price.data,
                stock_quantity=form.stock_quantity.data,
                stock_alert=form.stock_alert.data,
                unit=form.unit.data,
                carton_quantity=form.carton_quantity.data,
                category_id=form.category_id.data or None,
                is_active=form.is_active.data,
                tenant_id=current_user.tenant_id
            )
            
            # Handle image upload
            if form.image.data:
                s3_service = S3Service()
                image_url = s3_service.upload_product_image(form.image.data, product.id)
                product.image_url = image_url
            
            db.session.add(product)
            db.session.commit()
            
            flash('Product created successfully!', 'success')
            return redirect(url_for('products.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating product: {str(e)}', 'danger')
    
    return render_template('products/create.html', form=form)

@bp.route('/edit/<product_id>', methods=['GET', 'POST'])
@login_required
def edit(product_id):
    product = Product.query.filter_by(
        id=product_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    form = ProductForm(obj=product)
    form.category_id.choices = [('', 'Select Category')] + [
        (str(cat.id), cat.name) for cat in 
        Category.query.filter_by(tenant_id=current_user.tenant_id).all()
    ]
    
    if form.validate_on_submit():
        try:
            product.name = form.name.data
            product.description = form.description.data
            product.sku = form.sku.data
            product.barcode = form.barcode.data
            product.price = form.price.data
            product.cost_price = form.cost_price.data
            product.stock_quantity = form.stock_quantity.data
            product.stock_alert = form.stock_alert.data
            product.unit = form.unit.data
            product.carton_quantity = form.carton_quantity.data
            product.category_id = form.category_id.data or None
            product.is_active = form.is_active.data
            
            # Handle image upload
            if form.image.data:
                s3_service = S3Service()
                image_url = s3_service.upload_product_image(form.image.data, product.id)
                product.image_url = image_url
            
            db.session.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('products.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')
    
    return render_template('products/edit.html', form=form, product=product)

@bp.route('/delete/<product_id>', methods=['POST'])
@login_required
def delete(product_id):
    product = Product.query.filter_by(
        id=product_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    try:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'danger')
    
    return redirect(url_for('products.index'))

@bp.route('/categories')
@login_required
def categories():
    categories = Category.query.filter_by(tenant_id=current_user.tenant_id).all()
    form = CategoryForm()
    return render_template('products/categories.html', categories=categories, form=form)

@bp.route('/categories/create', methods=['POST'])
@login_required
def create_category():
    form = CategoryForm()
    if form.validate_on_submit():
        category = Category(
            name=form.name.data,
            description=form.description.data,
            tenant_id=current_user.tenant_id
        )
        db.session.add(category)
        db.session.commit()
        flash('Category created successfully!', 'success')
    return redirect(url_for('products.categories'))

@bp.route('/categories/update/<int:category_id>', methods=['POST'])
@login_required
def update_category(category_id):
    category = Category.query.filter_by(
        id=category_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    form = CategoryForm()
    if form.validate_on_submit():
        try:
            category.name = form.name.data
            category.description = form.description.data
            db.session.commit()
            flash('Category updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating category: {str(e)}', 'danger')
    
    return redirect(url_for('products.categories'))

@bp.route('/categories/delete/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    category = Category.query.filter_by(
        id=category_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    # Check if category has products
    product_count = Product.query.filter_by(category_id=category_id).count()
    if product_count > 0:
        flash('Cannot delete category that has products assigned to it.', 'danger')
        return redirect(url_for('products.categories'))
    
    try:
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting category: {str(e)}', 'danger')
    
    return redirect(url_for('products.categories'))

@bp.route('/api/search')
@login_required
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    products = Product.query.filter(
        Product.tenant_id == current_user.tenant_id,
        Product.is_active == True,
        db.or_(
            Product.name.ilike(f'%{query}%'),
            Product.sku.ilike(f'%{query}%'),
            Product.barcode.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': float(p.price),
        'stock_quantity': p.stock_quantity,
        'image_url': p.image_url,
        'sku': p.sku,
        'barcode': p.barcode
    } for p in products])