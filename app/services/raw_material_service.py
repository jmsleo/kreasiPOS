from app import db
from app.models import RawMaterial, StockAdjustment
from flask import current_app
from sqlalchemy import or_
from typing import List, Optional, Dict, Any
import uuid
import time

class RawMaterialService:
    """Service class for Raw Material operations"""
    
    @staticmethod
    def create_raw_material(tenant_id: str, name: str, description: str = None, sku: str = None, 
                          unit: str = 'kg', cost_price: float = None, stock_quantity: float = 0, 
                          stock_alert: float = 10, is_active: bool = True) -> RawMaterial:
        """
        Create a new raw material
        
        Args:
            tenant_id (str): Tenant ID
            name (str): Material name
            description (str): Material description
            sku (str): Stock Keeping Unit
            unit (str): Unit of measurement
            cost_price (float): Cost per unit
            stock_quantity (float): Initial stock quantity (support decimal)
            stock_alert (float): Low stock alert threshold (support decimal)
            is_active (bool): Active status
            
        Returns:
            RawMaterial: Created raw material
        """
        try:
            # PERBAIKAN: Auto-generate SKU jika kosong
            if not sku or sku.strip() == '':
                sku = RawMaterialService._generate_sku(tenant_id, name)
            
            # PERBAIKAN: Convert to float and handle None values
            cost_price_float = float(cost_price) if cost_price is not None else None
            stock_quantity_float = float(stock_quantity) if stock_quantity is not None else 0.0
            stock_alert_float = float(stock_alert) if stock_alert is not None else 10.0
            
            # PERBAIKAN: Validate stock cannot be negative
            if stock_quantity_float < 0:
                raise ValueError("Stock quantity cannot be negative")
            
            if stock_alert_float < 0:
                raise ValueError("Stock alert cannot be negative")
            
            raw_material = RawMaterial(
                tenant_id=tenant_id,
                name=name.strip(),
                description=description.strip() if description else None,
                sku=sku.strip(),
                unit=unit,
                cost_price=cost_price_float,
                stock_quantity=stock_quantity_float,
                stock_alert=stock_alert_float,
                is_active=is_active
            )
            
            db.session.add(raw_material)
            db.session.commit()
            
            current_app.logger.info(f"Raw material created: {name} (ID: {raw_material.id}, SKU: {sku})")
            return raw_material
            
        except ValueError as ve:
            db.session.rollback()
            current_app.logger.warning(f"Validation error creating raw material: {str(ve)}")
            raise ve
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating raw material: {str(e)}")
            raise
    
    @staticmethod
    def _generate_sku(tenant_id: str, name: str) -> str:
        """
        Generate unique SKU for raw material
        
        Args:
            tenant_id (str): Tenant ID
            name (str): Material name
            
        Returns:
            str: Generated SKU
        """
        try:
            # Ambil 3 huruf pertama dari nama (uppercase)
            name_prefix = ''.join(c for c in name if c.isalpha())[:3].upper()
            if len(name_prefix) < 3:
                name_prefix = name_prefix.ljust(3, 'X')
            
            # Tambahkan timestamp untuk uniqueness
            timestamp = str(int(time.time()))[-6:]  # 6 digit terakhir
            
            # Format: RM-[PREFIX]-[TIMESTAMP]
            base_sku = f"RM-{name_prefix}-{timestamp}"
            
            # Pastikan SKU unik dalam tenant
            counter = 1
            sku = base_sku
            while RawMaterial.query.filter_by(tenant_id=tenant_id, sku=sku).first():
                sku = f"{base_sku}-{counter:02d}"
                counter += 1
                if counter > 99:  # Failsafe
                    sku = f"RM-{str(uuid.uuid4())[:8].upper()}"
                    break
            
            return sku
            
        except Exception as e:
            current_app.logger.error(f"Error generating SKU: {str(e)}")
            # Fallback to UUID-based SKU
            return f"RM-{str(uuid.uuid4())[:8].upper()}"
    
    @staticmethod
    def update_raw_material(raw_material_id: str, user_id: str = None, **kwargs) -> RawMaterial:
        """
        Update existing raw material with proper stock tracking
        
        Args:
            raw_material_id (str): Raw material ID
            user_id (str): User performing the update
            **kwargs: Fields to update
            
        Returns:
            RawMaterial: Updated raw material
        """
        try:
            raw_material = RawMaterial.query.get(raw_material_id)
            if not raw_material:
                raise ValueError("Raw material not found")
            
            # Store original stock for comparison
            original_stock = raw_material.stock_quantity or 0.0
            
            # PERBAIKAN: Handle float conversions and validations
            if 'stock_quantity' in kwargs and kwargs['stock_quantity'] is not None:
                new_stock = float(kwargs['stock_quantity'])
                if new_stock < 0:
                    raise ValueError("Stock quantity cannot be negative")
                
                # PERBAIKAN: Track stock changes when editing
                if new_stock != original_stock and user_id:
                    stock_change = new_stock - original_stock
                    RawMaterialService._create_stock_adjustment(
                        raw_material_id=raw_material_id,
                        user_id=user_id,
                        adjustment_type='edit',
                        quantity_before=original_stock,
                        quantity_after=new_stock,
                        quantity_changed=stock_change,
                        reason='Manual edit via form',
                        notes=f'Stock updated from {original_stock} to {new_stock}'
                    )
                
                kwargs['stock_quantity'] = new_stock
            
            if 'stock_alert' in kwargs and kwargs['stock_alert'] is not None:
                kwargs['stock_alert'] = float(kwargs['stock_alert'])
                if kwargs['stock_alert'] < 0:
                    raise ValueError("Stock alert cannot be negative")
            
            if 'cost_price' in kwargs and kwargs['cost_price'] is not None:
                kwargs['cost_price'] = float(kwargs['cost_price'])
                if kwargs['cost_price'] < 0:
                    raise ValueError("Cost price cannot be negative")
            
            # PERBAIKAN: Auto-generate SKU jika kosong saat update
            if 'sku' in kwargs and (not kwargs['sku'] or kwargs['sku'].strip() == ''):
                kwargs['sku'] = RawMaterialService._generate_sku(raw_material.tenant_id, kwargs.get('name', raw_material.name))
            
            # Update allowed fields
            allowed_fields = ['name', 'description', 'sku', 'unit', 'cost_price', 
                            'stock_quantity', 'stock_alert', 'is_active']
            
            for field, value in kwargs.items():
                if field in allowed_fields and hasattr(raw_material, field):
                    # PERBAIKAN: Strip string fields
                    if isinstance(value, str):
                        value = value.strip()
                    setattr(raw_material, field, value)
            
            db.session.commit()
            
            current_app.logger.info(f"Raw material updated: {raw_material.name} (ID: {raw_material_id})")
            return raw_material
            
        except ValueError as ve:
            db.session.rollback()
            current_app.logger.warning(f"Validation error updating raw material: {str(ve)}")
            raise ve
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating raw material: {str(e)}")
            raise
    
    @staticmethod
    def _create_stock_adjustment(raw_material_id: str, user_id: str, adjustment_type: str,
                               quantity_before: float, quantity_after: float, quantity_changed: float,
                               reason: str = None, notes: str = None) -> StockAdjustment:
        """
        Create stock adjustment record for tracking
        
        Args:
            raw_material_id (str): Raw material ID
            user_id (str): User ID
            adjustment_type (str): Type of adjustment
            quantity_before (float): Stock before change
            quantity_after (float): Stock after change
            quantity_changed (float): Amount changed
            reason (str): Reason for adjustment
            notes (str): Additional notes
            
        Returns:
            StockAdjustment: Created adjustment record
        """
        try:
            raw_material = RawMaterial.query.get(raw_material_id)
            if not raw_material:
                raise ValueError("Raw material not found")
            
            adjustment = StockAdjustment(
                tenant_id=raw_material.tenant_id,
                raw_material_id=raw_material_id,
                user_id=user_id,
                adjustment_type=adjustment_type,
                quantity_before=quantity_before,
                quantity_after=quantity_after,
                quantity_changed=quantity_changed,
                reason=reason,
                notes=notes
            )
            
            db.session.add(adjustment)
            db.session.flush()  # Get ID without committing
            
            return adjustment
            
        except Exception as e:
            current_app.logger.error(f"Error creating stock adjustment: {str(e)}")
            raise
    
    @staticmethod
    def delete_raw_material(raw_material_id: str) -> bool:
        """
        Delete raw material (soft delete by setting is_active=False)
        
        Args:
            raw_material_id (str): Raw material ID
            
        Returns:
            bool: Success status
        """
        try:
            raw_material = RawMaterial.query.get(raw_material_id)
            if not raw_material:
                raise ValueError("Raw material not found")
            
            # PERBAIKAN: Check if raw material is used in any active BOM
            from app.models import BOMItem
            bom_usage = BOMItem.query.join('bom_header').filter(
                BOMItem.raw_material_id == raw_material_id,
                BOMItem.bom_header.has(is_active=True)
            ).count()
            
            if bom_usage > 0:
                # Soft delete to maintain BOM integrity
                raw_material.is_active = False
                current_app.logger.info(f"Raw material soft-deleted (used in BOM): {raw_material.name}")
            else:
                # Hard delete if not used in active BOMs
                db.session.delete(raw_material)
                current_app.logger.info(f"Raw material hard-deleted: {raw_material.name}")
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting raw material: {str(e)}")
            raise
    
    @staticmethod
    def get_raw_materials(tenant_id: str, include_inactive: bool = False, search: str = None, 
                         page: int = 1, per_page: int = 20) -> Any:
        """
        Get raw materials for a tenant with pagination and search
        
        Args:
            tenant_id (str): Tenant ID
            include_inactive (bool): Include inactive materials
            search (str): Search term for name or SKU
            page (int): Page number
            per_page (int): Items per page
            
        Returns:
            Pagination: Paginated raw materials
        """
        try:
            query = RawMaterial.query.filter_by(tenant_id=tenant_id)
            
            if not include_inactive:
                query = query.filter_by(is_active=True)
            
            if search and search.strip():
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        RawMaterial.name.ilike(search_term),
                        RawMaterial.sku.ilike(search_term),
                        RawMaterial.description.ilike(search_term)
                    )
                )
            
            return query.order_by(RawMaterial.name).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
        except Exception as e:
            current_app.logger.error(f"Error getting raw materials: {str(e)}")
            # Return empty pagination object instead of None
            from sqlalchemy.orm import Query
            empty_query = Query([])
            return empty_query.paginate(page=page, per_page=per_page, error_out=False)
    
    @staticmethod
    def get_low_stock_materials(tenant_id: str) -> List[RawMaterial]:
        """
        Get raw materials that are low on stock
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            list: Raw materials with low stock
        """
        try:
            return RawMaterial.query.filter(
                RawMaterial.tenant_id == tenant_id,
                RawMaterial.is_active == True,
                RawMaterial.stock_quantity <= RawMaterial.stock_alert
            ).order_by(RawMaterial.stock_quantity).all()
            
        except Exception as e:
            current_app.logger.error(f"Error getting low stock materials: {str(e)}")
            return []
    
    @staticmethod
    def update_stock(raw_material_id: str, quantity: float, operation: str = 'add', 
                    user_id: str = None, reason: str = None, notes: str = None) -> RawMaterial:
        """
        Update raw material stock with proper tracking
        
        Args:
            raw_material_id (str): Raw material ID
            quantity (float): Quantity to add or subtract (support decimal)
            operation (str): 'add' or 'subtract'
            user_id (str): User performing the operation
            reason (str): Reason for stock update
            notes (str): Additional notes
            
        Returns:
            RawMaterial: Updated raw material
        """
        try:
            raw_material = RawMaterial.query.get(raw_material_id)
            if not raw_material:
                raise ValueError("Raw material not found")
            
            # PERBAIKAN: Convert to float and validate
            quantity_float = float(quantity)
            if quantity_float <= 0:
                raise ValueError("Quantity must be positive")
            
            original_stock = raw_material.stock_quantity or 0.0
            
            if operation == 'add':
                new_stock = original_stock + quantity_float
                stock_change = quantity_float
            elif operation == 'subtract':
                new_stock = original_stock - quantity_float
                if new_stock < 0:
                    raise ValueError(f"Insufficient stock. Current: {original_stock}, Attempting to subtract: {quantity_float}")
                stock_change = -quantity_float
            else:
                raise ValueError("Invalid operation. Use 'add' or 'subtract'")
            
            # Update stock
            raw_material.stock_quantity = new_stock
            
            # Create stock adjustment record if user_id provided
            if user_id:
                adjustment_type = f'manual_{operation}'
                RawMaterialService._create_stock_adjustment(
                    raw_material_id=raw_material_id,
                    user_id=user_id,
                    adjustment_type=adjustment_type,
                    quantity_before=original_stock,
                    quantity_after=new_stock,
                    quantity_changed=stock_change,
                    reason=reason or f'Manual {operation}',
                    notes=notes
                )
            
            db.session.commit()
            
            current_app.logger.info(
                f"Stock updated for {raw_material.name}: {operation} {quantity_float}, "
                f"from {original_stock} to {new_stock}"
            )
            return raw_material
            
        except ValueError as ve:
            db.session.rollback()
            current_app.logger.warning(f"Validation error updating stock: {str(ve)}")
            raise ve
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating stock: {str(e)}")
            raise
    
    @staticmethod
    def get_stock_usage_report(tenant_id: str, start_date: Optional[str] = None, 
                              end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get raw material usage report
        
        Args:
            tenant_id (str): Tenant ID
            start_date (str): Start date for report
            end_date (str): End date for report
            
        Returns:
            dict: Usage report data
        """
        try:
            materials = RawMaterial.query.filter_by(
                tenant_id=tenant_id, 
                is_active=True
            ).order_by(RawMaterial.name).all()
            
            report_materials = []
            total_value = 0.0
            
            for material in materials:
                # PERBAIKAN: Calculate total value safely
                cost_price = material.cost_price or 0.0
                stock_quantity = material.stock_quantity or 0.0
                material_value = cost_price * stock_quantity
                total_value += material_value
                
                # PERBAIKAN: Get BOM usage information
                bom_items_count = material.bom_items.count()
                bom_products = []
                
                if bom_items_count > 0:
                    # Get products that use this material
                    for bom_item in material.bom_items:
                        if bom_item.bom_header and bom_item.bom_header.product:
                            bom_products.append({
                                'product_name': bom_item.bom_header.product.name,
                                'quantity_used': bom_item.quantity,
                                'unit': material.unit
                            })
                
                report_materials.append({
                    'material_id': material.id,
                    'material_name': material.name,
                    'sku': material.sku,
                    'current_stock': stock_quantity,
                    'stock_alert': material.stock_alert or 0.0,
                    'unit': material.unit,
                    'cost_price': cost_price,
                    'total_value': material_value,
                    'is_low_stock': material.is_low_stock(),
                    'bom_usage_count': bom_items_count,
                    'bom_products': bom_products,
                    'status': 'Active' if material.is_active else 'Inactive'
                })
            
            return {
                'materials': report_materials,
                'total_value': total_value,
                'material_count': len(materials)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting stock usage report: {str(e)}")
            return {
                'materials': [],
                'total_value': 0.0,
                'material_count': 0
            }
    
    @staticmethod
    def get_material_by_sku(tenant_id: str, sku: str) -> Optional[RawMaterial]:
        """
        Get raw material by SKU
        
        Args:
            tenant_id (str): Tenant ID
            sku (str): Stock Keeping Unit
            
        Returns:
            RawMaterial: Raw material or None
        """
        try:
            return RawMaterial.query.filter_by(
                tenant_id=tenant_id, 
                sku=sku, 
                is_active=True
            ).first()
        except Exception as e:
            current_app.logger.error(f"Error getting material by SKU: {str(e)}")
            return None
    
    @staticmethod
    def validate_stock_for_bom(raw_material_id: str, required_quantity: float) -> tuple:
        """
        Validate if raw material has sufficient stock for BOM
        
        Args:
            raw_material_id (str): Raw material ID
            required_quantity (float): Required quantity
            
        Returns:
            tuple: (bool, str) - (is_sufficient, message)
        """
        try:
            raw_material = RawMaterial.query.get(raw_material_id)
            if not raw_material:
                return False, "Raw material not found"
            
            if not raw_material.is_active:
                return False, "Raw material is inactive"
            
            current_stock = raw_material.stock_quantity or 0.0
            required_quantity_float = float(required_quantity)
            
            if current_stock < required_quantity_float:
                return False, f"Insufficient stock. Available: {current_stock} {raw_material.unit}, Required: {required_quantity_float}"
            
            return True, "Stock sufficient"
            
        except Exception as e:
            current_app.logger.error(f"Error validating stock: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def get_stock_adjustment_history(raw_material_id: str, limit: int = 50) -> List[StockAdjustment]:
        """
        Get stock adjustment history for a raw material
        
        Args:
            raw_material_id (str): Raw material ID
            limit (int): Maximum number of records to return
            
        Returns:
            List[StockAdjustment]: List of stock adjustments
        """
        try:
            return StockAdjustment.query.filter_by(
                raw_material_id=raw_material_id
            ).order_by(StockAdjustment.created_at.desc()).limit(limit).all()
            
        except Exception as e:
            current_app.logger.error(f"Error getting stock adjustment history: {str(e)}")
            return []