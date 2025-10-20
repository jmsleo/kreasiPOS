from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import json
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    """Always store in UTC, display will be converted by timezone utils"""
    return datetime.utcnow()

class DestinationType(Enum):
    PRODUCT = 'product'
    RAW_MATERIAL = 'raw_material'
    
class Tenant(db.Model):
    __tablename__ = 'tenants'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)  # UUID length 36
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    subdomain = db.Column(db.String(50), unique=True)
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Hardware settings
    printer_type = db.Column(db.String(20), default='thermal')
    printer_settings = db.Column(db.Text, default='{"type": "network", "host": "localhost", "port": 9100, "width": 42}')  # Changed to Text
    barcode_scanner_type = db.Column(db.String(20), default='keyboard')
    
    # Relationships
    users = db.relationship('User', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    products = db.relationship('Product', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    sales = db.relationship('Sale', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    customers = db.relationship('Customer', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    categories = db.relationship('Category', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')
    raw_materials = db.relationship('RawMaterial', backref='tenant', lazy='dynamic', cascade='all, delete-orphan')

class MarketplaceItem(db.Model):
    __tablename__ = 'marketplace_item'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    sku = db.Column(db.String(50), unique=True)
    image_url = db.Column(db.String(500))
    
    # Enhancement: Item type differentiation
    item_type = db.Column(db.Enum('product', 'raw_material', name='item_type_enum'), default='product')
    target_model = db.Column(db.String(20), default='product')
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
class RestockStatus(Enum):
    PENDING = 'pending'
    VERIFIED = 'verified'
    REJECTED = 'rejected'

class RestockOrder(db.Model):
    __tablename__ = 'restock_orders'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    marketplace_item_id = db.Column(db.String(36), db.ForeignKey('marketplace_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    #pilihan bahan baku atau produk
    destination_type = db.Column(db.String(20), nullable=False, default='product', server_default='product')
    # Alamat pengiriman untuk order ini (bisa berbeda dari alamat default tenant)
    shipping_address = db.Column(db.Text)
    shipping_city = db.Column(db.String(100))
    shipping_postal_code = db.Column(db.String(20))
    shipping_phone = db.Column(db.String(20))
    
    payment_proof_url = db.Column(db.String(500))
    status = db.Column(db.Enum(RestockStatus), default=RestockStatus.PENDING)
    notes = db.Column(db.Text)  # Notes dari tenant
    admin_notes = db.Column(db.Text)  # Notes dari admin
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    verified_at = db.Column(db.DateTime)
    verified_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Relationships - FIXED: use back_populates instead of backref
    tenant = db.relationship('Tenant')
    marketplace_item = db.relationship('MarketplaceItem')
    verifier = db.relationship('User')

class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(100))
    account_name = db.Column(db.String(100))
    qr_code_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)  # UUID length 36
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))  # Increased length for hashed password
    role = db.Column(db.String(20), nullable=False, default='cashier')
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    is_superadmin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    last_login = db.Column(db.DateTime)
    
    # Foreign keys
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_manager(self):
        return self.role in ['admin', 'manager']
    
    def is_cashier(self):
        return self.role in ['admin', 'manager', 'cashier']
    
    def get_id(self):
        return self.id

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Foreign keys
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    
    # Relationships
    products = db.relationship('Product', backref='category', lazy='dynamic')

# NEW MODEL: Raw Materials
class RawMaterial(db.Model):
    __tablename__ = 'raw_materials'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(100), unique=True)
    unit = db.Column(db.String(20), default='kg')
    cost_price = db.Column(db.Float)
    stock_quantity = db.Column(db.Float, default=0.0)  # Changed to Float for decimal support
    stock_alert = db.Column(db.Float, default=10.0)    # Changed to Float for decimal support
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Foreign keys
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    
    # Relationships
    bom_items = db.relationship('BOMItem', backref='raw_material', lazy='dynamic')
    
    def is_low_stock(self):
        """Check if raw material is low on stock"""
        return self.stock_quantity <= self.stock_alert
    
    def update_stock(self, quantity):
        """Update stock quantity (positive for addition, negative for deduction) with decimal precision"""
        # Convert to Decimal for precise calculation
        current_stock = Decimal(str(self.stock_quantity or 0))
        quantity_decimal = Decimal(str(quantity))
        
        new_stock = current_stock + quantity_decimal
        
        # Ensure stock doesn't go below 0
        if new_stock < 0:
            new_stock = Decimal('0')
        
        # Round to 6 decimal places and convert back to float
        self.stock_quantity = float(new_stock.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'sku': self.sku,
            'unit': self.unit,
            'cost_price': self.cost_price,
            'stock_quantity': self.stock_quantity,
            'stock_alert': self.stock_alert,
            'is_low_stock': self.is_low_stock()
        }

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(100), unique=True)
    barcode = db.Column(db.String(100))
    price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float)
    stock_quantity = db.Column(db.Integer, default=0)
    stock_alert = db.Column(db.Integer, default=10)
    unit = db.Column(db.String(20), default='pcs')  # pcs, carton
    carton_quantity = db.Column(db.Integer, default=1)  # pieces per carton
    is_active = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(500))
    
    # Enhancement: Flexible Stock Tracking & BOM
    requires_stock_tracking = db.Column(db.Boolean, default=True)
    has_bom = db.Column(db.Boolean, default=False)
    bom_cost = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Foreign keys
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    category_id = db.Column(db.String(36), db.ForeignKey('categories.id'))
    
    # Relationships
    sale_items = db.relationship('SaleItem', backref='product', lazy='dynamic')
    bom_headers = db.relationship('BOMHeader', backref='product', lazy='dynamic')
    
    def calculate_bom_cost(self):
        """Calculate total cost based on active BOM with decimal precision"""
        active_bom = self.bom_headers.filter_by(is_active=True).first()
        if active_bom:
            total_cost = Decimal('0')
            for bom_item in active_bom.items:
                if bom_item.raw_material and bom_item.raw_material.cost_price:
                    item_quantity = Decimal(str(bom_item.quantity))
                    item_cost = Decimal(str(bom_item.raw_material.cost_price))
                    total_cost += item_quantity * item_cost
            
            # Round to 6 decimal places and convert back to float
            self.bom_cost = float(total_cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))
            return self.bom_cost
        return 0
    
    def check_bom_availability(self, quantity=1):
        """Check if raw materials are available for BOM production with decimal precision"""
        if not self.has_bom:
            return True
            
        active_bom = self.bom_headers.filter_by(is_active=True).first()
        if not active_bom:
            return True
            
        for bom_item in active_bom.items:
            if not bom_item.raw_material:
                continue  # Skip jika raw_material tidak ada
                
            # Use Decimal for precise calculation
            bom_quantity = Decimal(str(bom_item.quantity))
            product_quantity = Decimal(str(quantity))
            required_quantity = bom_quantity * product_quantity
            
            # Pastikan stock_quantity tidak None
            current_stock = Decimal(str(bom_item.raw_material.stock_quantity or 0))
            if current_stock < required_quantity:
                return False
        return True
    
    def process_bom_deduction(self, quantity=1):
        """Deduct raw materials based on BOM when product is sold with decimal precision"""
        if not self.has_bom:
            return True
            
        active_bom = self.bom_headers.filter_by(is_active=True).first()
        if not active_bom:
            return True
        
        # Log the BOM deduction process
        from flask import current_app
        current_app.logger.info(f"Processing BOM deduction for product {self.name}, quantity: {quantity}")
            
        for bom_item in active_bom.items:
            if not bom_item.raw_material:
                continue  # Skip jika raw_material tidak ada
                
            # Use Decimal for precise calculation
            bom_quantity = Decimal(str(bom_item.quantity))
            product_quantity = Decimal(str(quantity))
            required_quantity = bom_quantity * product_quantity
            
            # Log each raw material deduction
            current_app.logger.info(f"  - {bom_item.raw_material.name}: BOM qty {bom_quantity} x Product qty {product_quantity} = Required {required_quantity}")
            current_app.logger.info(f"    Current stock: {bom_item.raw_material.stock_quantity}")
            
            # PERBAIKAN: Pastikan stok cukup sebelum pengurangan
            current_stock = Decimal(str(bom_item.raw_material.stock_quantity or 0))
            if current_stock < required_quantity:
                current_app.logger.error(f"    Insufficient stock for {bom_item.raw_material.name}: need {required_quantity}, have {current_stock}")
                return False
            
            # Use the update_stock method which handles decimal precision
            bom_item.raw_material.update_stock(-float(required_quantity))
            
            current_app.logger.info(f"    New stock: {bom_item.raw_material.stock_quantity}")
        
        # Commit dilakukan di level service/route, bukan di model
        return True
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'stock_quantity': self.stock_quantity,
            'image_url': self.image_url,
            'sku': self.sku,
            'barcode': self.barcode,
            'requires_stock_tracking': self.requires_stock_tracking,
            'has_bom': self.has_bom,
            'bom_cost': self.bom_cost,
            'bom_available': self.check_bom_availability() if self.has_bom else True
        }
    
    @property
    def last_sale_item(self):
        """Get the last sale item for this product"""
        return self.sale_items.order_by(SaleItem.id.desc()).first()
    
    @property 
    def total_revenue(self):
        """Calculate total revenue from this product"""
        return db.session.query(db.func.sum(SaleItem.total_price))\
            .filter(SaleItem.product_id == self.id)\
            .scalar() or 0

# NEW MODEL: BOM Header
class BOMHeader(db.Model):
    __tablename__ = 'bom_headers'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'), nullable=False)
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    items = db.relationship('BOMItem', backref='bom_header', lazy='dynamic', cascade='all, delete-orphan')
    
    def calculate_total_cost(self):
        """Calculate total cost of all raw materials in this BOM with decimal precision"""
        total_cost = Decimal('0')
        for item in self.items:
            if item.raw_material and item.raw_material.cost_price:
                item_quantity = Decimal(str(item.quantity))
                item_cost = Decimal(str(item.raw_material.cost_price))
                total_cost += item_quantity * item_cost
        
        # Round to 6 decimal places and return as float
        return float(total_cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))
    
    def validate_availability(self, quantity=1):
        """Validate if all raw materials are available for production with decimal precision"""
        for item in self.items:
            bom_quantity = Decimal(str(item.quantity))
            product_quantity = Decimal(str(quantity))
            required_quantity = bom_quantity * product_quantity
            
            current_stock = Decimal(str(item.raw_material.stock_quantity or 0))
            if current_stock < required_quantity:
                return False, f"Insufficient {item.raw_material.name}: need {required_quantity}, have {current_stock}"
        return True, "All materials available"

# NEW MODEL: BOM Items
class BOMItem(db.Model):
    __tablename__ = 'bom_items'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    bom_header_id = db.Column(db.String(36), db.ForeignKey('bom_headers.id'), nullable=False)
    raw_material_id = db.Column(db.String(36), db.ForeignKey('raw_materials.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # Support decimal quantities
    unit = db.Column(db.String(20))
    notes = db.Column(db.Text)
    
    def to_dict(self):
        total_cost = 0
        if self.raw_material and self.raw_material.cost_price:
            # Use Decimal for precise calculation
            quantity_decimal = Decimal(str(self.quantity))
            cost_decimal = Decimal(str(self.raw_material.cost_price))
            total_cost = float((quantity_decimal * cost_decimal).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))
        
        return {
            'id': self.id,
            'raw_material_id': self.raw_material_id,
            'raw_material_name': self.raw_material.name if self.raw_material else '',
            'quantity': self.quantity,
            'unit': self.unit,
            'cost_per_unit': self.raw_material.cost_price if self.raw_material else 0,
            'total_cost': total_cost
        }

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    loyalty_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Foreign keys
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    
    # Relationships
    sales = db.relationship('Sale', backref='customer', lazy='dynamic')
    
    @property
    def last_sale_date(self):
        """Get the date of the last sale for this customer"""
        last_sale = self.sales.order_by(Sale.created_at.desc()).first()
        return last_sale.created_at if last_sale else None
    
    @property
    def total_spent(self):
        """Calculate total amount spent by customer"""
        return db.session.query(db.func.sum(Sale.total_amount))\
            .filter(Sale.customer_id == self.id)\
            .scalar() or 0
    
    @property 
    def sales_count(self):
        """Get total number of sales"""
        return self.sales.count()

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, card, transfer
    payment_status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)
    
    # Foreign keys
    tenant_id = db.Column(db.String(36), db.ForeignKey('tenants.id'), nullable=False)
    customer_id = db.Column(db.String(36), db.ForeignKey('customers.id'))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Relationships
    user = db.relationship('User', backref='sales')
    items = db.relationship('SaleItem', backref='sale', lazy='dynamic', cascade='all, delete-orphan')
    
    def calculate_totals(self):
        """Calculate totals from sale items"""
        subtotal = sum(item.total_price for item in self.items)
        self.total_amount = subtotal + self.tax_amount - self.discount_amount

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    # Foreign keys
    sale_id = db.Column(db.String(36), db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.String(36), db.ForeignKey('products.id'), nullable=False)
    
    @property
    def product_name(self):
        return self.product.name

@login_manager.user_loader
def load_user(user_id):
    from app.models import User  # Import lokal untuk menghindari circular import
    return User.query.get(user_id)

class MaintenanceSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    message = db.Column(db.Text, default='System under maintenance')
    start_time = db.Column(db.DateTime, nullable=True)
    estimated_end_time = db.Column(db.DateTime, nullable=True)
    allowed_emails = db.Column(db.JSON, default=list)  # List email yang boleh akses
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'is_active': self.is_active,
            'message': self.message,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'estimated_end_time': self.estimated_end_time.isoformat() if self.estimated_end_time else None,
            'allowed_emails': self.allowed_emails or [],
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }