from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.customers import bp
from app.customers.forms import CustomerForm, CustomerSearchForm
from app.models import Customer, db
from sqlalchemy import or_

@bp.route('/customers')
@login_required
def index():
    """Display all customers with pagination and search"""
    page = request.args.get('page', 1, type=int)
    search_form = CustomerSearchForm()
    
    # Handle search
    search_query = request.args.get('search', '')
    if search_query:
        customers = Customer.query.filter(
            Customer.tenant_id == current_user.tenant_id,
            or_(
                Customer.name.ilike(f'%{search_query}%'),
                Customer.email.ilike(f'%{search_query}%'),
                Customer.phone.ilike(f'%{search_query}%')
            )
        ).order_by(Customer.name).paginate(
            page=page, per_page=10, error_out=False
        )
        search_form.search.data = search_query
    else:
        customers = Customer.query.filter_by(
            tenant_id=current_user.tenant_id
        ).order_by(Customer.name).paginate(
            page=page, per_page=10, error_out=False
        )
    
    return render_template('customers/index.html', 
                         customers=customers,
                         search_form=search_form,
                         title='Customers')

@bp.route('/customers/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new customer"""
    form = CustomerForm()
    
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            tenant_id=current_user.tenant_id
        )
        
        db.session.add(customer)
        db.session.commit()
        
        flash(f'Customer {customer.name} has been created successfully!', 'success')
        return redirect(url_for('customers.index'))
    
    return render_template('customers/create.html', 
                         form=form, 
                         title='Add New Customer')

@bp.route('/customers/<string:customer_id>')
@login_required
def detail(customer_id):
    """View customer details"""
    customer = Customer.query.filter_by(
        id=customer_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    return render_template('customers/detail.html', 
                         customer=customer,
                         title=f'Customer - {customer.name}')

@bp.route('/customers/<string:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(customer_id):
    """Edit customer information"""
    customer = Customer.query.filter_by(
        id=customer_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    form = CustomerForm(obj=customer)
    
    if form.validate_on_submit():
        customer.name = form.name.data
        customer.email = form.email.data
        customer.phone = form.phone.data
        customer.address = form.address.data
        
        db.session.commit()
        
        flash(f'Customer {customer.name} has been updated successfully!', 'success')
        return redirect(url_for('customers.detail', customer_id=customer.id))
    
    return render_template('customers/edit.html', 
                         form=form, 
                         customer=customer,
                         title=f'Edit - {customer.name}')

@bp.route('/customers/<string:customer_id>/delete', methods=['POST'])
@login_required
def delete(customer_id):
    """Delete customer"""
    customer = Customer.query.filter_by(
        id=customer_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    customer_name = customer.name
    db.session.delete(customer)
    db.session.commit()
    
    flash(f'Customer {customer_name} has been deleted successfully!', 'success')
    return redirect(url_for('customers.index'))

# API Routes for AJAX operations
@bp.route('/api/customers')
@login_required
def api_customers():
    """API endpoint for customers data (for select2, etc)"""
    search = request.args.get('q', '')
    
    if search:
        customers = Customer.query.filter(
            Customer.tenant_id == current_user.tenant_id,
            or_(
                Customer.name.ilike(f'%{search}%'),
                Customer.phone.ilike(f'%{search}%')
            )
        ).limit(10).all()
    else:
        customers = Customer.query.filter_by(
            tenant_id=current_user.tenant_id
        ).limit(10).all()
    
    results = [{
        'id': customer.id,
        'text': f"{customer.name} ({customer.phone})" if customer.phone else customer.name,
        'name': customer.name,
        'phone': customer.phone,
        'email': customer.email
    } for customer in customers]
    
    return jsonify({'results': results})

@bp.route('/api/customers/<int:customer_id>')
@login_required
def api_customer_detail(customer_id):
    """API endpoint for customer details"""
    customer = Customer.query.filter_by(
        id=customer_id, 
        tenant_id=current_user.tenant_id
    ).first_or_404()
    
    return jsonify({
        'id': customer.id,
        'name': customer.name,
        'email': customer.email,
        'phone': customer.phone,
        'address': customer.address
    })