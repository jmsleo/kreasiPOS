from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, DecimalField, SelectField, HiddenField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, NumberRange, Optional, Length
from app.models import Product, Customer

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

class CustomerSelectForm(FlaskForm):
    customer = SelectField('Customer', coerce=int, validators=[Optional()])

    def __init__(self, *args, **kwargs):
        super(CustomerSelectForm, self).__init__(*args, **kwargs)
        self.customer.choices = [('', 'Walk-in Customer')] + [(c.id, c.name) for c in Customer.query.order_by(Customer.name).all()]

# NEW: Refund Forms
class RefundForm(FlaskForm):
    """Form for creating a refund"""
    refund_reason = SelectField('Alasan Refund', choices=[
        ('defective', 'Produk Rusak/Cacat'),
        ('wrong_item', 'Barang Salah'),
        ('customer_request', 'Permintaan Pelanggan'),
        ('expired', 'Produk Kadaluarsa'),
        ('damaged_shipping', 'Rusak saat Pengiriman'),
        ('other', 'Lainnya')
    ], validators=[DataRequired(message='Alasan refund wajib dipilih')])
    
    notes = TextAreaField('Catatan Tambahan', validators=[
        Optional(),
        Length(max=500, message='Catatan maksimal 500 karakter')
    ], description='Catatan tambahan tentang refund (opsional)')
    
    submit = SubmitField('Proses Refund')

class RefundItemForm(FlaskForm):
    """Form for individual refund items"""
    sale_item_id = HiddenField(validators=[DataRequired()])
    product_name = StringField('Produk', render_kw={'readonly': True})
    original_quantity = IntegerField('Qty Asli', render_kw={'readonly': True})
    refunded_quantity = IntegerField('Sudah Direfund', render_kw={'readonly': True})
    refund_quantity = IntegerField('Qty Refund', validators=[
        DataRequired(message='Jumlah refund wajib diisi'),
        NumberRange(min=1, message='Jumlah refund minimal 1')
    ])
    unit_price = DecimalField('Harga Satuan', places=2, render_kw={'readonly': True})
    refund_amount = DecimalField('Total Refund', places=2, render_kw={'readonly': True})

class RefundSearchForm(FlaskForm):
    """Form for searching refundable sales"""
    search_type = SelectField('Cari Berdasarkan', choices=[
        ('receipt_number', 'Nomor Struk'),
        ('customer_name', 'Nama Pelanggan'),
        ('date', 'Tanggal')
    ], default='receipt_number')
    
    search_value = StringField('Kata Kunci', validators=[
        DataRequired(message='Kata kunci pencarian wajib diisi'),
        Length(min=2, max=100, message='Kata kunci harus 2-100 karakter')
    ])
    
    days_limit = SelectField('Periode Pencarian', choices=[
        ('7', '7 hari terakhir'),
        ('14', '14 hari terakhir'),
        ('30', '30 hari terakhir'),
        ('60', '60 hari terakhir'),
        ('90', '90 hari terakhir')
    ], default='30')
    
    submit = SubmitField('Cari Transaksi')

class ProcessRefundForm(FlaskForm):
    """Form for processing pending refunds"""
    refund_id = HiddenField(validators=[DataRequired()])
    action = SelectField('Aksi', choices=[
        ('process', 'Proses Refund'),
        ('cancel', 'Batalkan Refund')
    ], validators=[DataRequired()])
    
    admin_notes = TextAreaField('Catatan Admin', validators=[
        Optional(),
        Length(max=500, message='Catatan maksimal 500 karakter')
    ], description='Catatan dari admin/manager (opsional)')
    
    submit = SubmitField('Konfirmasi')

class RefundReportForm(FlaskForm):
    """Form for refund reports"""
    start_date = StringField('Tanggal Mulai', validators=[DataRequired()], 
                           render_kw={'type': 'date'})
    end_date = StringField('Tanggal Akhir', validators=[DataRequired()], 
                         render_kw={'type': 'date'})
    
    status_filter = SelectField('Filter Status', choices=[
        ('', 'Semua Status'),
        ('pending', 'Pending'),
        ('completed', 'Selesai'),
        ('cancelled', 'Dibatalkan')
    ], validators=[Optional()])
    
    reason_filter = SelectField('Filter Alasan', choices=[
        ('', 'Semua Alasan'),
        ('defective', 'Produk Rusak/Cacat'),
        ('wrong_item', 'Barang Salah'),
        ('customer_request', 'Permintaan Pelanggan'),
        ('expired', 'Produk Kadaluarsa'),
        ('damaged_shipping', 'Rusak saat Pengiriman'),
        ('other', 'Lainnya')
    ], validators=[Optional()])
    
    submit = SubmitField('Generate Report')