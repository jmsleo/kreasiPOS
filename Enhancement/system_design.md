# System Design Document
# POS RSS Enhancement - Inventory Management & BOM System

## 1. Implementation Approach

Kami akan melakukan enhancement pada sistem POS RSS yang sudah ada dengan menambahkan fitur-fitur berikut secara bertahap:

### 1.1 Flexible Stock Tracking
- Menambahkan field `requires_stock_tracking` pada model Product
- Mengimplementasikan logika conditional stock deduction pada proses penjualan
- Memperbarui laporan inventory untuk mengecualikan produk non-tracking

### 1.2 Raw Materials Management
- Membuat model `RawMaterial` terpisah dengan struktur mirip Product
- Mengimplementasikan CRUD operations untuk raw materials
- Menambahkan sistem alert untuk low stock raw materials

### 1.3 BOM (Bill of Materials) System
- Membuat model `BOMHeader` dan `BOMItem` untuk struktur BOM
- Mengimplementasikan BOM calculation engine
- Integrasi BOM deduction dengan sales process

### 1.4 Enhanced Marketplace
- Menambahkan field `item_type` pada MarketplaceItem
- Mengimplementasikan dual-flow inventory (Product vs Raw Material)
- Memperbarui restock process untuk handle kedua jenis item

### 1.5 Improved Reporting
- Memperbaiki chart interactivity di reports
- Menambahkan BOM cost analysis
- Mengimplementasikan raw material usage tracking

## 2. User & UI Interaction Patterns

### 2.1 Product Management Enhancement
**Scenario 1: Creating Product with Flexible Stock Tracking**
- User mengakses Product Create Form
- User mengisi data produk standar
- User memilih checkbox "Requires Stock Tracking" (default: checked)
- Jika unchecked, field stock quantity menjadi optional
- User dapat mengaktifkan "Enable BOM" untuk produk yang memerlukan

**Scenario 2: BOM Configuration**
- User mengakses BOM Configuration dari Product Detail
- User menambahkan raw materials dengan quantity
- System menghitung estimated cost berdasarkan raw material prices
- User dapat save/update BOM configuration

### 2.2 Marketplace Enhancement
**Scenario 3: Purchasing Raw Materials**
- User mengakses Marketplace
- User memilih item type filter (Product/Raw Material)
- User melakukan purchase dengan menentukan jenis item
- System memproses purchase sesuai dengan item type

### 2.3 Sales Process with BOM
**Scenario 4: Processing Sale with BOM Products**
- Cashier menambahkan produk ke cart
- System mengecek apakah produk memiliki BOM
- System memvalidasi ketersediaan raw materials
- Jika insufficient, system memberikan warning
- Setelah sale confirmed, system mendeduct raw materials sesuai BOM

## 3. System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │  Application    │    │  Business       │
│   Layer         │    │  Layer          │    │  Logic Layer    │
│                 │    │                 │    │                 │
│ - Web UI        │───▶│ - Flask Routes  │───▶│ - Product Svc   │
│ - JavaScript    │    │ - Forms (WTF)   │    │ - BOM Service   │
│ - Bootstrap     │    │ - Auth          │    │ - RawMat Svc    │
│                 │    │ - Middleware    │    │ - Inventory Svc │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐           │
│  External       │    │  Data Access    │           │
│  Services       │    │  Layer          │           │
│                 │    │                 │           │
│ - AWS S3        │───▶│ - SQLAlchemy    │◀──────────┘
│ - Email Service │    │ - DB Models     │
│ - Printer Svc   │    │ - Migrations    │
└─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │    Database     │
                       │                 │
                       │ - products      │
                       │ - raw_materials │
                       │ - bom_headers   │
                       │ - bom_items     │
                       │ - marketplace   │
                       └─────────────────┘
```

## 4. UI Navigation Flow

```
[Home Dashboard] ──┐
                   │
    ┌──────────────┼──────────────┐
    │              │              │
[Products]    [Marketplace]   [Sales/POS]
    │              │              │
    ├─[Create]     ├─[Browse]     ├─[Process Sale]
    ├─[Edit]       ├─[Purchase]   ├─[History]
    ├─[BOM Config] ├─[Orders]     └─[Reports]
    └─[Categories] └─[My Address]
         │
    [Raw Materials]
         │
    ├─[Create]
    ├─[Edit]
    ├─[Stock Alert]
    └─[Usage Report]
```

## 5. Data Structures and Interfaces

### 5.1 Enhanced Product Model
```python
class Product(db.Model):
    # Existing fields...
    requires_stock_tracking: bool = True
    has_bom: bool = False
    bom_cost: float = 0.0
    
    def calculate_bom_cost(self) -> float
    def check_bom_availability(self, quantity: int) -> bool
```

### 5.2 New Raw Material Model
```python
class RawMaterial(db.Model):
    id: str
    name: str
    sku: str
    unit: str
    cost_price: float
    stock_quantity: int
    stock_alert: int
    tenant_id: str
    
    def is_low_stock(self) -> bool
    def update_stock(self, quantity: int) -> void
```

### 5.3 BOM Models
```python
class BOMHeader(db.Model):
    id: str
    product_id: str
    version: int
    is_active: bool
    
    def calculate_total_cost(self) -> float
    def validate_availability(self, quantity: int) -> bool

class BOMItem(db.Model):
    id: str
    bom_header_id: str
    raw_material_id: str
    quantity: float
    unit: str
```

### 5.4 Service Interfaces
```python
class IBOMService:
    def create_bom(self, product_id: str, items: list) -> BOMHeader
    def process_bom_deduction(self, bom_id: str, quantity: int) -> bool
    def validate_bom_availability(self, bom_id: str, quantity: int) -> bool

class IInventoryService:
    def process_marketplace_purchase(self, order: RestockOrder) -> void
    def process_sale_deduction(self, sale: Sale) -> void
    def get_inventory_status(self, tenant_id: str) -> dict
```

## 6. Program Call Flow

### 6.1 BOM Product Sale Process
```
1. Cashier adds BOM-enabled product to cart
2. System calls BOMService.validate_bom_availability()
3. BOMService checks each raw material availability
4. If sufficient, sale proceeds
5. After sale confirmation:
   - SalesService.process_sale() creates Sale record
   - SalesService calls BOMService.process_bom_deduction()
   - BOMService deducts raw materials based on BOM recipe
   - InventoryService updates raw material stocks
```

### 6.2 Marketplace Purchase Flow
```
1. Tenant selects item from marketplace
2. System checks item_type (product/raw_material)
3. RestockOrder created with appropriate target_model
4. Admin verifies order
5. If verified:
   - If item_type = "product": Add to Product inventory
   - If item_type = "raw_material": Add to RawMaterial inventory
6. InventoryService processes the stock addition
```

### 6.3 Flexible Stock Tracking
```
1. During sale processing, check product.requires_stock_tracking
2. If True: Perform normal stock deduction
3. If False: Skip stock quantity validation and deduction
4. BOM products still process raw material deduction regardless
```

## 7. Database ER Overview

### 7.1 Core Relationships
- `products` 1:N `bom_headers` (One product can have multiple BOM versions)
- `bom_headers` 1:N `bom_items` (One BOM contains multiple raw materials)
- `bom_items` N:1 `raw_materials` (Multiple BOM items can use same raw material)
- `marketplace_item` 1:N `restock_orders` (One item can have multiple orders)
- `tenants` 1:N `raw_materials` (Tenant isolation for raw materials)

### 7.2 Key Constraints
- BOM items must reference valid raw materials within same tenant
- Only one active BOM per product at a time
- Raw material stock cannot go negative (with configurable override)
- Marketplace item_type must match target inventory model

## 8. API Design Patterns

### 8.1 RESTful Endpoints
```
# Raw Materials
GET    /api/raw-materials              # List raw materials
POST   /api/raw-materials              # Create raw material
GET    /api/raw-materials/{id}         # Get raw material
PUT    /api/raw-materials/{id}         # Update raw material
DELETE /api/raw-materials/{id}         # Delete raw material

# BOM Management
GET    /api/products/{id}/bom          # Get product BOM
POST   /api/products/{id}/bom          # Create/Update BOM
DELETE /api/products/{id}/bom          # Delete BOM
POST   /api/bom/validate               # Validate BOM availability

# Enhanced Marketplace
GET    /api/marketplace?type=raw_material  # Filter by item type
POST   /api/marketplace/purchase            # Purchase with type specification
```

### 8.2 Request/Response Formats
```json
// BOM Creation Request
POST /api/products/{id}/bom
{
    "items": [
        {
            "raw_material_id": "rm-123",
            "quantity": 0.5,
            "unit": "kg"
        }
    ],
    "notes": "Standard recipe v1.0"
}

// BOM Validation Response
POST /api/bom/validate
{
    "valid": true,
    "total_cost": 12.50,
    "availability": [
        {
            "raw_material_id": "rm-123",
            "required": 1.0,
            "available": 25.5,
            "sufficient": true
        }
    ]
}
```

## 9. Unclear Aspects & Assumptions

### 9.1 Technical Assumptions
1. **BOM Complexity**: Sistem saat ini tidak mendukung nested BOM (BOM dalam BOM). Implementasi dimulai dengan flat BOM structure.

2. **Unit Conversion**: Tidak ada automatic unit conversion. Raw materials dan BOM items harus menggunakan unit yang konsisten.

3. **Stock Validation**: Ketika raw material tidak cukup untuk BOM, sistem akan memberikan warning tetapi tetap memungkinkan penjualan (configurable per tenant).

4. **Cost Calculation**: BOM cost akan di-update real-time saat raw material cost berubah, bukan snapshot saat BOM dibuat.

### 9.2 Business Logic Clarifications
1. **Multi-tenant Raw Materials**: Raw materials strictly isolated per tenant, tidak ada sharing antar tenant.

2. **Chart Interactivity**: Perbaikan chart akan mencakup drill-down sampai level daily breakdown dan product-wise analysis.

3. **Marketplace Approval**: Raw materials yang dibeli dari marketplace langsung masuk ke inventory setelah admin verification, tanpa additional approval workflow.

### 9.3 Performance Considerations
1. **BOM Calculation**: Untuk produk dengan BOM kompleks, perhitungan availability akan di-cache untuk menghindari repeated database queries.

2. **Inventory Updates**: Stock updates akan menggunakan database transactions untuk memastikan consistency.

3. **Reporting**: Chart data akan di-cache dengan TTL 5 menit untuk mengurangi database load.

---

*Dokumen ini akan diupdate seiring dengan development progress dan feedback dari stakeholders.*