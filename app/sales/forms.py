from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, DecimalField, SelectField, HiddenField 
from wtforms.validators import DataRequired, NumberRange, Optional
from app.models import Product

class QuickSaleForm(FlaskForm):
    product_id = SelectField('Product', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('Quantity', default=1, validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Add to Cart')

    def __init__(self, *args, **kwargs):
        super(QuickSaleForm, self).__init__(*args, **kwargs)
        self.product_id.choices = [(p.id, f"{p.name} - ${p.price:.2f}") 
                                 for p in Product.query.order_by(Product.name).all()]

class SaleForm(FlaskForm):
    customer_id = SelectField('Customer', coerce=int, validators=[Optional()])
    payment_method = SelectField('Payment Method', 
                               choices=[('cash', 'Cash'), ('card', 'Card'), ('transfer', 'Transfer')],
                               validators=[DataRequired()])
    total_amount = DecimalField('Total Amount', places=2, validators=[DataRequired()])
    submit = SubmitField('Complete Sale')