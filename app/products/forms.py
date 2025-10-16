from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SelectField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length, Optional
from flask_wtf.file import FileField, FileAllowed

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    sku = StringField('SKU', validators=[DataRequired(), Length(max=100)])
    barcode = StringField('Barcode', validators=[Optional(), Length(max=100)])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    cost_price = FloatField('Cost Price', validators=[Optional(), NumberRange(min=0)])
    stock_quantity = IntegerField('Stock Quantity', validators=[DataRequired(), NumberRange(min=0)])
    stock_alert = IntegerField('Low Stock Alert', validators=[DataRequired(), NumberRange(min=0)])
    unit = SelectField('Unit', choices=[('pcs', 'Pieces'), ('carton', 'Carton')], default='pcs')
    carton_quantity = IntegerField('Pieces per Carton', validators=[Optional(), NumberRange(min=1)], default=1)
    category_id = SelectField('Category', coerce=str, validators=[Optional()])
    is_active = BooleanField('Active', default=True)
    image = FileField('Product Image', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    submit = SubmitField('Save Product')

class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Save Category')