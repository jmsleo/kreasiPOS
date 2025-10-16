from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, TextAreaField, SubmitField, BooleanField, PasswordField
from wtforms.validators import DataRequired, Optional, Length, NumberRange, Email, EqualTo, ValidationError
from app.models import User

class TenantInfoForm(FlaskForm):
    name = StringField('Store Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Address', validators=[Optional()])
    submit = SubmitField('Update Store Info')

class PrinterSettingsForm(FlaskForm):
    printer_type = SelectField('Printer Type', choices=[
        ('thermal', 'Thermal Receipt Printer'),
        ('label', 'Label Printer'),
        ('network', 'Network Printer')
    ], default='thermal')
    printer_host = StringField('Printer IP/Host', validators=[Optional()])
    printer_port = IntegerField('Port', default=9100, validators=[Optional(), NumberRange(min=1, max=65535)])
    printer_width = IntegerField('Paper Width', default=42, validators=[NumberRange(min=32, max=80)])
    submit = SubmitField('Save Printer Settings')

class HardwareSettingsForm(FlaskForm):
    barcode_scanner_type = SelectField('Barcode Scanner Type', choices=[
        ('keyboard', 'Keyboard Emulation'),
        ('serial', 'Serial Port'),
        ('bluetooth', 'Bluetooth')
    ], default='keyboard')
    submit = SubmitField('Save Hardware Settings')

class UserForm(FlaskForm):
    """
    Form untuk membuat dan mengedit pengguna (kasir) oleh tenant admin.
    """
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    # Pilihan peran, saat ini hanya 'cashier' yang bisa dibuat oleh tenant_admin.
    role = SelectField('Role', choices=[('cashier', 'Cashier')], validators=[DataRequired()])
    # Password bersifat opsional saat mengedit, tapi wajib saat membuat.
    password = PasswordField('Password', validators=[
        Optional(),
        Length(min=6, message='Password must be at least 6 characters long.'),
        EqualTo('confirm_password', message='Passwords must match.')
    ])
    confirm_password = PasswordField('Confirm Password')
    submit = SubmitField('Save User')

    def __init__(self, original_email=None, *args, **kwargs):
        """
        Constructor kustom untuk menangani validasi email unik saat edit.
        """
        super(UserForm, self).__init__(*args, **kwargs)
        self.original_email = original_email

    def validate_email(self, email):
        """
        Memastikan email yang dimasukkan belum digunakan oleh pengguna lain.
        """
        # Hanya validasi jika email diubah.
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is already in use. Please choose a different one.')