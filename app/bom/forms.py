from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, SelectField, FieldList, FormField, HiddenField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length

class BOMItemForm(FlaskForm):
    raw_material_id = SelectField('Bahan Baku', validators=[DataRequired()], coerce=str)
    quantity = FloatField('Jumlah', validators=[DataRequired(), NumberRange(min=0.001)])
    unit = StringField('Unit', validators=[Optional(), Length(max=20)])
    notes = TextAreaField('Catatan', validators=[Optional(), Length(max=500)])

class BOMForm(FlaskForm):
    notes = TextAreaField('Catatan BOM', validators=[Optional(), Length(max=1000)])
    is_active = BooleanField('Active BOM', default=True)
    items = FieldList(FormField(BOMItemForm), min_entries=1)
    submit = SubmitField('Save BOM')

class BOMValidationForm(FlaskForm):
    product_id = HiddenField('Product ID', validators=[DataRequired()])
    quantity = FloatField('Jumlah Produksi', validators=[DataRequired(), NumberRange(min=1)], default=1)