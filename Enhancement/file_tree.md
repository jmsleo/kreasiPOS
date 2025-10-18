# File Structure Overview
# POS RSS Enhancement - Inventory Management & BOM System

## Recommended Project Structure

```
posrss/
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models.py                     # Enhanced with new models
│   ├── middleware/
│   │   └── tenant_middleware.py
│   ├── utils/
│   │   └── timezone.py
│   │
│   ├── auth/                         # Existing
│   │   ├── __init__.py
│   │   ├── forms.py
│   │   └── routes.py
│   │
│   ├── products/                     # Enhanced
│   │   ├── __init__.py
│   │   ├── forms.py                  # Enhanced with BOM fields
│   │   └── routes.py                 # Enhanced with BOM endpoints
│   │
│   ├── raw_materials/                # NEW MODULE
│   │   ├── __init__.py
│   │   ├── forms.py
│   │   └── routes.py
│   │
│   ├── bom/                          # NEW MODULE
│   │   ├── __init__.py
│   │   ├── forms.py
│   │   └── routes.py
│   │
│   ├── marketplace/                  # Enhanced
│   │   ├── __init__.py
│   │   ├── forms.py                  # Enhanced with item_type
│   │   └── routes.py                 # Enhanced purchase flow
│   │
│   ├── sales/                        # Enhanced
│   │   ├── __init__.py
│   │   ├── forms.py
│   │   └── routes.py                 # Enhanced with BOM processing
│   │
│   ├── reports/                      # Enhanced
│   │   ├── __init__.py
│   │   └── routes.py                 # Enhanced charts & BOM reports
│   │
│   ├── services/                     # Enhanced
│   │   ├── email_service.py
│   │   ├── printer_service.py
│   │   ├── s3_service.py
│   │   ├── bom_service.py            # NEW SERVICE
│   │   ├── raw_material_service.py   # NEW SERVICE
│   │   └── inventory_service.py      # NEW SERVICE
│   │
│   ├── customers/                    # Existing
│   │   ├── __init__.py
│   │   ├── forms.py
│   │   └── routes.py
│   │
│   ├── dashboard/                    # Enhanced
│   │   ├── __init__.py
│   │   └── routes.py                 # Enhanced with new metrics
│   │
│   ├── settings/                     # Existing
│   │   ├── __init__.py
│   │   ├── forms.py
│   │   └── routes.py
│   │
│   ├── superadmin/                   # Existing
│   │   ├── __init__.py
│   │   └── routes.py
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── main.css
│   │   │   ├── products.css          # Enhanced
│   │   │   ├── bom.css               # NEW
│   │   │   ├── raw-materials.css     # NEW
│   │   │   └── marketplace.css       # Enhanced
│   │   ├── js/
│   │   │   ├── main.js
│   │   │   ├── pos.js                # Enhanced with BOM validation
│   │   │   ├── products.js           # Enhanced with BOM management
│   │   │   ├── bom-management.js     # NEW
│   │   │   ├── raw-materials.js      # NEW
│   │   │   ├── marketplace.js        # Enhanced with item types
│   │   │   ├── reports.js            # Enhanced with chart fixes
│   │   │   └── inventory-alerts.js   # NEW
│   │   └── assets/
│   │       ├── images/
│   │       └── icons/
│   │
│   └── templates/
│       ├── base.html                 # Enhanced with new nav items
│       ├── auth/
│       │   ├── login.html
│       │   └── register.html
│       ├── products/                 # Enhanced
│       │   ├── index.html            # Enhanced with BOM indicators
│       │   ├── create.html           # Enhanced with BOM options
│       │   ├── edit.html             # Enhanced with BOM management
│       │   ├── categories.html
│       │   └── bom_config.html       # NEW
│       ├── raw_materials/            # NEW TEMPLATES
│       │   ├── index.html
│       │   ├── create.html
│       │   ├── edit.html
│       │   └── stock_alerts.html
│       ├── bom/                      # NEW TEMPLATES
│       │   ├── index.html
│       │   ├── create.html
│       │   ├── edit.html
│       │   └── cost_analysis.html
│       ├── marketplace/              # Enhanced
│       │   ├── index.html            # Enhanced with item type filters
│       │   ├── restock.html          # Enhanced with item type selection
│       │   ├── restock_orders.html
│       │   ├── manage.html           # Enhanced for superadmin
│       │   └── create_edit_item.html # Enhanced with item_type
│       ├── sales/                    # Enhanced
│       │   ├── pos.html              # Enhanced with BOM validation UI
│       │   ├── history.html
│       │   └── receipt.html
│       ├── reports/                  # Enhanced
│       │   ├── index.html            # Enhanced charts
│       │   ├── inventory.html        # Enhanced with raw materials
│       │   ├── bom_analysis.html     # NEW
│       │   └── cost_analysis.html    # NEW
│       ├── dashboard/                # Enhanced
│       │   └── index.html            # Enhanced with new KPIs
│       ├── customers/
│       │   ├── index.html
│       │   ├── create.html
│       │   └── edit.html
│       ├── settings/
│       │   └── index.html
│       ├── superadmin/
│       │   └── index.html
│       └── errors/
│           ├── 404.html
│           ├── 500.html
│           └── 403.html
│
├── migrations/                       # Enhanced
│   ├── versions/
│   │   ├── [existing migrations]
│   │   ├── xxx_add_product_enhancements.py      # NEW
│   │   ├── xxx_create_raw_materials.py          # NEW
│   │   ├── xxx_create_bom_tables.py             # NEW
│   │   └── xxx_enhance_marketplace.py           # NEW
│   ├── alembic.ini
│   ├── env.py
│   └── script.py.mako
│
├── docs/                             # Enhanced
│   ├── enhancement_prd.md
│   ├── system_design.md              # NEW
│   ├── architect.plantuml            # NEW
│   ├── class_diagram.plantuml        # NEW
│   ├── sequence_diagram.plantuml     # NEW
│   ├── er_diagram.plantuml           # NEW
│   ├── file_tree.md                  # NEW
│   ├── api_documentation.md          # NEW
│   └── deployment_guide.md           # NEW
│
├── tests/                            # Enhanced
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_models.py                # Enhanced with new models
│   ├── test_products.py              # Enhanced with BOM tests
│   ├── test_raw_materials.py         # NEW
│   ├── test_bom.py                   # NEW
│   ├── test_marketplace.py           # Enhanced
│   ├── test_sales.py                 # Enhanced with BOM tests
│   ├── test_services.py              # NEW
│   └── test_integration.py           # NEW
│
├── config.py                         # Existing
├── requirements.txt                  # Enhanced with new dependencies
├── run.py                           # Existing
├── reset_database.py                # Enhanced
├── Procfile                         # Existing
└── runtime.txt                      # Existing
```

## New Dependencies to Add

```txt
# Add to requirements.txt
sqlalchemy-utils>=0.38.0    # For enhanced model utilities
marshmallow>=3.19.0         # For API serialization
flask-marshmallow>=0.14.0   # Flask integration for marshmallow
celery>=5.2.0              # For background tasks (optional)
redis>=4.5.0               # For caching and task queue
```

## Key File Changes Summary

### 1. Enhanced Models (`app/models.py`)
- Add `requires_stock_tracking`, `has_bom`, `bom_cost` to Product
- Add new `RawMaterial`, `BOMHeader`, `BOMItem` models
- Add `item_type`, `target_model` to MarketplaceItem
- Enhanced relationships and methods

### 2. New Service Classes
- `BOMService`: Handle BOM CRUD and calculations
- `RawMaterialService`: Manage raw material operations
- `InventoryService`: Coordinate inventory operations across models

### 3. Enhanced Routes
- Products: Add BOM management endpoints
- Marketplace: Add item type handling
- Sales: Add BOM processing logic
- Reports: Add new chart interactivity and BOM reports

### 4. New Templates
- BOM configuration interfaces
- Raw material management pages
- Enhanced marketplace with item type selection
- Improved reports with interactive charts

### 5. Enhanced JavaScript
- BOM management UI components
- Real-time stock validation
- Enhanced POS with BOM checking
- Fixed chart interactivity issues

### 6. Database Migrations
- Migration scripts for new tables and enhanced existing tables
- Data migration scripts for existing data compatibility

## Implementation Priority

### Phase 1: Core Infrastructure
1. Database migrations
2. Enhanced models
3. Basic service classes

### Phase 2: BOM System
1. BOM CRUD operations
2. BOM calculation logic
3. Integration with sales

### Phase 3: Marketplace Enhancement
1. Item type differentiation
2. Enhanced purchase flow
3. Inventory routing logic

### Phase 4: UI/UX Improvements
1. Enhanced forms and templates
2. JavaScript enhancements
3. Chart interactivity fixes

### Phase 5: Testing & Documentation
1. Comprehensive test coverage
2. API documentation
3. User guides and deployment docs

This structure maintains backward compatibility while adding the new functionality in a modular and maintainable way.