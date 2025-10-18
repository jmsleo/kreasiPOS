from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SubmitField, SelectField, BooleanField, FileField
from wtforms.validators import DataRequired, NumberRange, Optional, Length
from flask_wtf.file import FileAllowed  # HAPUS FileRequired dari sini

class MarketplaceItemForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    price = DecimalField('Price', validators=[DataRequired(), NumberRange(min=0)])
    stock = IntegerField('Stock Quantity', validators=[DataRequired(), NumberRange(min=0)])
    sku = StringField('SKU', validators=[Optional(), Length(max=50)])
    image = FileField('Product Image', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    submit = SubmitField('Save Item')

class RestockOrderForm(FlaskForm):
    """Form untuk restock order dengan opsi alamat"""
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1)])
    destination_type = SelectField(
        'Simpan Sebagai', 
        choices=[
            ('product', '🛍️ Produk (Untuk Dijual Kembali)'),
            ('raw_material', '🏭 Bahan Baku (Untuk Produksi)')
        ], 
        validators=[DataRequired()],
        description='Pilih tujuan pembelian: Produk untuk dijual langsung, Bahan Baku untuk diproduksi'
    )
    # Opsi alamat pengiriman
    use_default_address = BooleanField('Gunakan alamat default', default=True)
    shipping_address = TextAreaField('Alamat Pengiriman', validators=[Optional()])
    shipping_city = StringField('Kota Pengiriman', validators=[Optional()])
    shipping_postal_code = StringField('Kode Pos Pengiriman', validators=[Optional()])
    shipping_phone = StringField('Telepon Pengiriman', validators=[Optional()])
    
    payment_proof = FileField('Bukti Pembayaran', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Hanya gambar dan PDF!')
    ])
    notes = TextAreaField('Catatan untuk Admin', validators=[Optional()])

class RestockVerificationForm(FlaskForm):
    """Form untuk verifikasi admin"""
    status = SelectField('Status', choices=[
        ('verified', 'Terverifikasi'),
        ('rejected', 'Ditolak')
    ], validators=[DataRequired()])
    admin_notes = TextAreaField('Catatan Admin', validators=[Optional()])

class PaymentMethodForm(FlaskForm):
    name = StringField('Payment Method Name', validators=[DataRequired()])
    account_number = StringField('Account Number', validators=[DataRequired()])
    account_name = StringField('Account Name', validators=[DataRequired()])
    qr_code = FileField('QR Code Image', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])
    is_active = BooleanField('Active', default=True)

class TenantAddressForm(FlaskForm):
    """Form untuk mengelola alamat tenant"""
    address = TextAreaField('Alamat Lengkap', validators=[DataRequired()])
    city = StringField('Kota', validators=[DataRequired()])
    postal_code = StringField('Kode Pos', validators=[DataRequired()])
    phone = StringField('Nomor Telepon', validators=[DataRequired()])