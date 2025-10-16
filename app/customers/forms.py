from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, TelField, TextAreaField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional

class CustomerForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    email = EmailField('Email', validators=[Optional(), Email()])
    phone = TelField('Phone Number', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Address', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Save Customer')

class CustomerSearchForm(FlaskForm):
    search = StringField('Search Customers', validators=[Optional()])
    submit = SubmitField('Search')