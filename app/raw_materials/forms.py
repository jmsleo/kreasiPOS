from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, IntegerField, SelectField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from flask_wtf.file import FileField, FileAllowed  # Tambahkan ini untuk upload file
import re  # Untuk validasi SKU

class RawMaterialForm(FlaskForm):
    name = StringField('Nama Bahan Baku', validators=[
        DataRequired(message='Nama bahan baku wajib diisi'),
        Length(min=2, max=200, message='Nama harus antara 2-200 karakter')
    ])
    
    description = TextAreaField('Deskripsi', validators=[
        Optional(), 
        Length(max=1000, message='Deskripsi maksimal 1000 karakter')
    ])
    
    sku = StringField('SKU', validators=[
        Optional(), 
        Length(max=100, message='SKU maksimal 100 karakter'),
        # Validasi format SKU opsional
        # lambda form, field: re.match(r'^[A-Z0-9\-_]+$', field.data) if field.data else True
    ])
    
    unit = SelectField('Unit', choices=[
        ('', 'Pilih Satuan'),
        ('kg', 'Kilogram (kg)'),
        ('g', 'Gram (g)'),
        ('l', 'Liter (l)'),
        ('ml', 'Mililiter (ml)'),
        ('pcs', 'Pieces (pcs)'),
        ('m', 'Meter (m)'),
        ('cm', 'Centimeter (cm)'),
        ('box', 'Box'),
        ('pack', 'Pack'),
        ('unit', 'Unit'),
        ('buah', 'Buah'),
        ('lembar', 'Lembar'),
        ('roll', 'Roll'),
        ('botol', 'Botol'),
        ('kaleng', 'Kaleng')
    ], validators=[DataRequired(message='Satuan wajib dipilih')])
    
    cost_price = FloatField('Harga Cost per Unit', validators=[
        Optional(), 
        NumberRange(min=0, message='Harga tidak boleh negatif')
    ], description='Harga beli per satuan bahan baku')
    
    stock_quantity = FloatField('Stok Awal', validators=[  # Ubah ke FloatField
        DataRequired(message='Stok awal wajib diisi'), 
        NumberRange(min=0, message='Stok tidak boleh negatif')
    ], default=0, description='Jumlah stok saat ini')
    
    stock_alert = FloatField('Alert Stok Minimum', validators=[  # Ubah ke FloatField
        DataRequired(message='Alert stok wajib diisi'), 
        NumberRange(min=0, message='Alert stok tidak boleh negatif')
    ], default=10, description='System akan memberi peringatan saat stok mencapai level ini')
    
    is_active = BooleanField('Aktif', default=True)

class RawMaterialSearchForm(FlaskForm):
    search = StringField('Cari Bahan Baku', validators=[
        Optional(), 
        Length(max=100, message='Pencarian maksimal 100 karakter')
    ])
    include_inactive = BooleanField('Tampilkan yang Tidak Aktif', default=False)
    
    # Tambahkan filter tambahan
    unit_filter = SelectField('Filter Satuan', choices=[
        ('', 'Semua Satuan'),
        ('kg', 'Kilogram (kg)'),
        ('g', 'Gram (g)'),
        ('l', 'Liter (l)'),
        ('ml', 'Mililiter (ml)'),
        ('pcs', 'Pieces (pcs)'),
        ('m', 'Meter (m)'),
        ('cm', 'Centimeter (cm)'),
        ('box', 'Box'),
        ('pack', 'Pack')
    ], validators=[Optional()])
    
    stock_status = SelectField('Status Stok', choices=[
        ('', 'Semua Status'),
        ('low', 'Stok Rendah'),
        ('adequate', 'Stok Cukup'),
        ('out', 'Stok Habis')
    ], validators=[Optional()])

class StockUpdateForm(FlaskForm):
    operation = SelectField('Operasi', choices=[
        ('add', 'Tambah Stok'),
        ('subtract', 'Kurangi Stok')
    ], validators=[DataRequired(message='Jenis operasi wajib dipilih')])
    
    quantity = FloatField('Jumlah', validators=[  # Ubah ke FloatField
        DataRequired(message='Jumlah wajib diisi'), 
        NumberRange(min=0.01, message='Jumlah harus lebih dari 0')
    ])
    
    notes = TextAreaField('Catatan', validators=[
        Optional(), 
        Length(max=500, message='Catatan maksimal 500 karakter')
    ], description='Alasan penyesuaian stok (opsional)')
    
    # Tambahkan field untuk referensi
    reference_number = StringField('Nomor Referensi', validators=[
        Optional(),
        Length(max=50, message='Nomor referensi maksimal 50 karakter')
    ], description='No. PO, No. Invoice, dll (opsional)')
    
    adjustment_date = StringField('Tanggal Penyesuaian', validators=[
        DataRequired(message='Tanggal penyesuaian wajib diisi')
    ], description='Tanggal efektif penyesuaian stok')

# Form tambahan untuk bulk operations
class BulkStockUpdateForm(FlaskForm):
    update_type = SelectField('Jenis Update', choices=[
        ('percentage', 'Persentase'),
        ('fixed', 'Jumlah Tetap'),
        ('set', 'Set ke Nilai')
    ], validators=[DataRequired()])
    
    value = FloatField('Nilai', validators=[
        DataRequired(),
        NumberRange(min=0, message='Nilai tidak boleh negatif')
    ])
    
    materials = SelectField('Bahan Baku', choices=[], validators=[Optional()])
    # Untuk multiple selection, bisa menggunakan:
    # materials = SelectMultipleField('Bahan Baku', choices=[])

# Form untuk import dari Excel/CSV
class ImportMaterialsForm(FlaskForm):
    file = FileField('File Import', validators=[
        DataRequired(message='File wajib diupload'),
        FileAllowed(['csv', 'xlsx', 'xls'], 'Hanya file CSV dan Excel yang diizinkan')
    ])
    
    import_type = SelectField('Tipe Import', choices=[
        ('create', 'Buat Baru Saja'),
        ('update', 'Update yang Sudah Ada'),
        ('both', 'Buat Baru dan Update')
    ], default='both')

# Form untuk export data
class ExportMaterialsForm(FlaskForm):
    format = SelectField('Format', choices=[
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF')
    ], default='excel')
    
    include_inactive = BooleanField('Include Non-Aktif', default=False)
    columns = SelectField('Kolom', choices=[
        ('all', 'Semua Kolom'),
        ('basic', 'Informasi Dasar'),
        ('stock', 'Informasi Stok')
    ], default='all')

# Custom validators
def validate_sku_unique(form, field):
    """Validator untuk memastikan SKU unik"""
    from app.models import RawMaterial
    from flask import current_app
    
    if field.data:
        # Cek apakah SKU sudah ada (kecuali untuk record yang sedang diedit)
        existing = RawMaterial.query.filter_by(sku=field.data).first()
        if existing and hasattr(form, '_obj') and form._obj.id != existing.id:
            from wtforms.validators import ValidationError
            raise ValidationError('SKU sudah digunakan oleh bahan baku lain')

def validate_stock_alert(form, field):
    """Validator untuk memastikan stock_alert tidak terlalu tinggi"""
    if hasattr(form, 'stock_quantity') and form.stock_quantity.data:
        if field.data > form.stock_quantity.data * 10:  # Maksimal 10x stock quantity
            from wtforms.validators import ValidationError
            raise ValidationError('Alert stok terlalu tinggi dibandingkan stok saat ini')

def validate_cost_price(form, field):
    """Validator untuk harga cost yang realistis"""
    if field.data and field.data > 1000000000:  # Maksimal 1 Miliar
        from wtforms.validators import ValidationError
        raise ValidationError('Harga cost terlalu tinggi')

# Terapkan validators custom ke form yang sudah ada
# Tambahkan ke field yang sesuai:
# sku = StringField('SKU', validators=[..., validate_sku_unique])
# stock_alert = FloatField(..., validators=[..., validate_stock_alert])
# cost_price = FloatField(..., validators=[..., validate_cost_price])