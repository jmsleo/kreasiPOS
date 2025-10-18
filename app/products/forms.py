from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, IntegerField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, ValidationError
from app.models import Product
from flask_wtf.file import FileField, FileAllowed

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired(), Length(min=1, max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    sku = StringField('SKU', validators=[Optional(), Length(max=100)])
    barcode = StringField('Barcode', validators=[Optional(), Length(max=100)])
    price = FloatField('Selling Price', validators=[DataRequired(), NumberRange(min=0)])
    cost_price = FloatField('Cost Price', validators=[Optional(), NumberRange(min=0)])
    
    # Stock tracking fields
    requires_stock_tracking = BooleanField('Requires Stock Tracking', default=True)
    stock_quantity = IntegerField('Stock Quantity', validators=[Optional(), NumberRange(min=0)], default=0)
    stock_alert = IntegerField('Low Stock Alert', validators=[Optional(), NumberRange(min=0)], default=10)
    
    # BOM fields
    has_bom = BooleanField('Enable BOM (Bill of Materials)', default=False)
    
    unit = SelectField('Unit', choices=[
        ('pcs', 'Pieces (pcs)'),
        ('carton', 'Carton'),
        ('kg', 'Kilogram (kg)'),
        ('g', 'Gram (g)'),
        ('l', 'Liter (l)'),
        ('ml', 'Mililiter (ml)')
    ], default='pcs')
    carton_quantity = IntegerField('Pieces per Carton', validators=[Optional(), NumberRange(min=1)], default=1)
    category_id = SelectField('Category', validators=[Optional()], coerce=str)
    
    # Corrected field for image upload
    image = FileField('Image', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])

    is_active = BooleanField('Active', default=True)
    
    submit = SubmitField('Save Product')
    
    def validate_stock_quantity(self, field):
        if self.requires_stock_tracking.data and field.data is None:
            raise ValidationError('Stock quantity is required when stock tracking is enabled.')
    
    def validate_stock_alert(self, field):
        if self.requires_stock_tracking.data and field.data is None:
            raise ValidationError('Stock alert is required when stock tracking is enabled.')

class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Save Category') # Also adding a submit button here for consistency

class ProductSearchForm(FlaskForm):
    search = StringField('Search Products', validators=[Optional(), Length(max=100)])
    category_id = SelectField('Filter by Category', validators=[Optional()], coerce=str)

class StockAdjustmentForm(FlaskForm):
    adjustment_type = SelectField('Adjustment Type', choices=[
        ('add', 'Add Stock'),
        ('subtract', 'Subtract Stock'),
        ('set', 'Set Stock Level')
    ], validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    reason = TextAreaField('Reason', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Adjust Stock') # And here too