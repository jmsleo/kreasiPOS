from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, IntegerField, SelectField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, ValidationError
from flask_wtf.file import FileField, FileAllowed  # Tambahkan ini untuk upload file
import re  # Untuk validasi SKU
from app.models import RawMaterial
from flask_login import current_user

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
        Length(max=100, message='SKU maksimal 100 karakter')
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

    # PERBAIKAN: Tambahkan __init__ untuk menyimpan objek asli
    def __init__(self, *args, **kwargs):
        # Ambil 'original_object' yang kita kirim dari routes.py
        self.original_object = kwargs.pop('original_object', None)
        super(RawMaterialForm, self).__init__(*args, **kwargs)

    # PERBAIKAN: Logika validasi SKU yang lebih 'pintar'
    def validate_sku(self, field):
        """Custom validator untuk SKU yang unik dalam tenant"""
        
        submitted_sku = field.data.strip() if field.data else None
        
        if not submitted_sku:
            # Jika SKU dikosongkan (opsional), lewati validasi
            return

        # Cek apakah ini mode EDIT (kita mengirim 'original_object' dari route)
        if self.original_object:
            # Jika SKU yang disubmit SAMA DENGAN SKU asli di database,
            # berarti pengguna tidak mengubah SKU. Lewati validasi.
            if submitted_sku == self.original_object.sku:
                return

        # --- Jika kode sampai di sini, berarti: ---
        # 1. Ini adalah item BARU (self.original_object adalah None)
        # 2. Ini adalah item EDIT, dan pengguna MENGUBAH SKU-nya
        
        # Lakukan pengecekan ke database untuk SKU yang disubmit
        query = RawMaterial.query.filter(
            RawMaterial.sku == submitted_sku,
            RawMaterial.tenant_id == current_user.tenant_id
        )
        
        # (Jaga-jaga) Jika ini mode edit (dan SKU berubah),
        # pastikan tidak bertabrakan dengan item lain (meskipun sudah dicek di atas)
        if self.original_object:
             query = query.filter(RawMaterial.id != self.original_object.id)
        
        existing = query.first()
        if existing:
            # Jika ditemukan, SKU sudah dipakai
            raise ValidationError('SKU sudah digunakan oleh bahan baku lain dalam tenant ini')

    def validate_stock_alert(self, field):
        """Custom validator untuk stock_alert yang realistis"""
        if field.data and hasattr(self, 'stock_quantity') and self.stock_quantity.data:
            # Alert tidak boleh lebih dari 10x stock quantity (untuk mencegah nilai yang tidak masuk akal)
            if field.data > self.stock_quantity.data * 10:
                raise ValidationError('Alert stok terlalu tinggi dibandingkan stok saat ini')

    def validate_cost_price(self, field):
        """Custom validator untuk cost_price yang realistis"""
        if field.data and field.data > 1000000000:  # Maksimal 1 Miliar
            raise ValidationError('Harga cost terlalu tinggi')

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
    
    # PERBAIKAN: Mengubah DataRequired menjadi Optional
    adjustment_date = StringField('Tanggal Penyesuaian', validators=[
        Optional()
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