"""
Enhanced Inventory Service dengan Redis Cache Integration
Mengoptimalkan inventory operations dengan caching layer
"""
from typing import Dict, List, Optional, Tuple
from flask import current_app
from app.models import Product, RawMaterial, Sale, SaleItem, BOMHeader, BOMItem
from app.extensions import db
from app.services.cache_service import (
    InventoryCacheService, 
    ProductCacheService, 
    BOMCacheService,
    cache_result
)
from datetime import datetime, timedelta
import json


class EnhancedInventoryService:
    """Enhanced inventory service dengan Redis caching"""
    
    @staticmethod
    @cache_result(timeout='short', key_prefix='inventory_status')
    def get_inventory_status(tenant_id: str) -> Dict:
        """Get comprehensive inventory status dengan caching"""
        try:
            # Check cache first
            cached_data = InventoryCacheService.get_cached_stock_levels(tenant_id)
            if cached_data:
                return cached_data
            
            # Query database jika tidak ada cache
            products = Product.query.filter_by(tenant_id=tenant_id).all()
            raw_materials = RawMaterial.query.filter_by(tenant_id=tenant_id).all()
            
            inventory_status = {
                'products': {
                    'total_items': len(products),
                    'low_stock_count': 0,
                    'out_of_stock_count': 0,
                    'items': []
                },
                'raw_materials': {
                    'total_items': len(raw_materials),
                    'low_stock_count': 0,
                    'out_of_stock_count': 0,
                    'items': []
                },
                'total_value': 0.0,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            # Process products
            for product in products:
                if product.requires_stock_tracking:
                    item_data = {
                        'id': product.id,
                        'name': product.name,
                        'sku': product.sku,
                        'stock_quantity': product.stock_quantity,
                        'stock_alert': product.stock_alert,
                        'selling_price': float(product.selling_price),
                        'is_low_stock': product.stock_quantity <= product.stock_alert,
                        'is_out_of_stock': product.stock_quantity <= 0
                    }
                    
                    if item_data['is_low_stock']:
                        inventory_status['products']['low_stock_count'] += 1
                    if item_data['is_out_of_stock']:
                        inventory_status['products']['out_of_stock_count'] += 1
                    
                    inventory_status['products']['items'].append(item_data)
                    inventory_status['total_value'] += product.stock_quantity * float(product.selling_price)
            
            # Process raw materials
            for raw_material in raw_materials:
                item_data = {
                    'id': raw_material.id,
                    'name': raw_material.name,
                    'sku': raw_material.sku,
                    'stock_quantity': raw_material.stock_quantity,
                    'stock_alert': raw_material.stock_alert,
                    'cost_price': float(raw_material.cost_price),
                    'unit': raw_material.unit,
                    'is_low_stock': raw_material.stock_quantity <= raw_material.stock_alert,
                    'is_out_of_stock': raw_material.stock_quantity <= 0
                }
                
                if item_data['is_low_stock']:
                    inventory_status['raw_materials']['low_stock_count'] += 1
                if item_data['is_out_of_stock']:
                    inventory_status['raw_materials']['out_of_stock_count'] += 1
                
                inventory_status['raw_materials']['items'].append(item_data)
                inventory_status['total_value'] += raw_material.stock_quantity * float(raw_material.cost_price)
            
            # Cache the result
            InventoryCacheService.cache_stock_levels(tenant_id, inventory_status)
            
            return inventory_status
            
        except Exception as e:
            current_app.logger.error(f"Error getting inventory status for tenant {tenant_id}: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def get_low_stock_alerts(tenant_id: str) -> List[Dict]:
        """Get low stock alerts dengan caching"""
        try:
            # Check cache first
            cached_alerts = InventoryCacheService.get_cached_low_stock_alerts(tenant_id)
            if cached_alerts:
                return cached_alerts
            
            alerts = []
            
            # Check products
            low_stock_products = Product.query.filter(
                Product.tenant_id == tenant_id,
                Product.requires_stock_tracking == True,
                Product.stock_quantity <= Product.stock_alert
            ).all()
            
            for product in low_stock_products:
                alerts.append({
                    'type': 'product',
                    'id': product.id,
                    'name': product.name,
                    'sku': product.sku,
                    'current_stock': product.stock_quantity,
                    'alert_level': product.stock_alert,
                    'severity': 'critical' if product.stock_quantity <= 0 else 'warning',
                    'category': 'Product'
                })
            
            # Check raw materials
            low_stock_raw_materials = RawMaterial.query.filter(
                RawMaterial.tenant_id == tenant_id,
                RawMaterial.stock_quantity <= RawMaterial.stock_alert
            ).all()
            
            for raw_material in low_stock_raw_materials:
                alerts.append({
                    'type': 'raw_material',
                    'id': raw_material.id,
                    'name': raw_material.name,
                    'sku': raw_material.sku,
                    'current_stock': raw_material.stock_quantity,
                    'alert_level': raw_material.stock_alert,
                    'severity': 'critical' if raw_material.stock_quantity <= 0 else 'warning',
                    'category': 'Raw Material',
                    'unit': raw_material.unit
                })
            
            # Sort by severity (critical first)
            alerts.sort(key=lambda x: (x['severity'] == 'warning', x['name']))
            
            # Cache the alerts
            InventoryCacheService.cache_low_stock_alerts(tenant_id, alerts)
            
            return alerts
            
        except Exception as e:
            current_app.logger.error(f"Error getting low stock alerts for tenant {tenant_id}: {str(e)}")
            return []
    
    @staticmethod
    def process_sale_deduction(sale: Sale) -> bool:
        """Process inventory deduction untuk sale dengan cache invalidation"""
        try:
            tenant_id = sale.tenant_id
            
            for sale_item in sale.items:
                product = sale_item.product
                
                # Handle regular stock tracking products
                if product.requires_stock_tracking:
                    if product.stock_quantity < sale_item.quantity:
                        current_app.logger.warning(
                            f"Insufficient stock for product {product.name}. "
                            f"Required: {sale_item.quantity}, Available: {product.stock_quantity}"
                        )
                        # Bisa di-configure apakah tetap lanjut atau tidak
                    
                    product.stock_quantity -= sale_item.quantity
                
                # Handle BOM products
                if product.has_bom:
                    EnhancedInventoryService._process_bom_deduction(
                        product.id, sale_item.quantity, tenant_id
                    )
                
                # Invalidate product cache
                ProductCacheService.invalidate_product_cache(product.id, tenant_id)
            
            # Commit changes
            db.session.commit()
            
            # Invalidate inventory cache
            InventoryCacheService.invalidate_inventory_cache(tenant_id)
            
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing sale deduction: {str(e)}")
            return False
    
    @staticmethod
    def _process_bom_deduction(product_id: str, quantity: int, tenant_id: str) -> bool:
        """Process BOM raw material deduction"""
        try:
            # Get active BOM
            bom_header = BOMHeader.query.filter_by(
                product_id=product_id,
                is_active=True
            ).first()
            
            if not bom_header:
                return True  # No BOM, skip
            
            # Process each BOM item
            for bom_item in bom_header.items:
                required_quantity = bom_item.quantity * quantity
                raw_material = bom_item.raw_material
                
                if raw_material.stock_quantity < required_quantity:
                    current_app.logger.warning(
                        f"Insufficient raw material {raw_material.name}. "
                        f"Required: {required_quantity}, Available: {raw_material.stock_quantity}"
                    )
                
                raw_material.stock_quantity -= required_quantity
            
            # Invalidate BOM cache
            BOMCacheService.invalidate_bom_cache(product_id, tenant_id)
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error processing BOM deduction: {str(e)}")
            return False
    
    @staticmethod
    def update_product_stock(product_id: str, quantity: int, tenant_id: str, operation: str = 'add') -> bool:
        """Update product stock dengan cache invalidation"""
        try:
            product = Product.query.filter_by(id=product_id, tenant_id=tenant_id).first()
            if not product:
                return False
            
            if operation == 'add':
                product.stock_quantity += quantity
            elif operation == 'subtract':
                if product.stock_quantity < quantity:
                    current_app.logger.warning(f"Insufficient stock for product {product.name}")
                product.stock_quantity -= quantity
            elif operation == 'set':
                product.stock_quantity = quantity
            
            db.session.commit()
            
            # Invalidate caches
            ProductCacheService.invalidate_product_cache(product_id, tenant_id)
            InventoryCacheService.invalidate_inventory_cache(tenant_id)
            
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating product stock: {str(e)}")
            return False
    
    @staticmethod
    def update_raw_material_stock(raw_material_id: str, quantity: int, tenant_id: str, operation: str = 'add') -> bool:
        """Update raw material stock dengan cache invalidation"""
        try:
            raw_material = RawMaterial.query.filter_by(id=raw_material_id, tenant_id=tenant_id).first()
            if not raw_material:
                return False
            
            if operation == 'add':
                raw_material.stock_quantity += quantity
            elif operation == 'subtract':
                if raw_material.stock_quantity < quantity:
                    current_app.logger.warning(f"Insufficient stock for raw material {raw_material.name}")
                raw_material.stock_quantity -= quantity
            elif operation == 'set':
                raw_material.stock_quantity = quantity
            
            db.session.commit()
            
            # Invalidate inventory cache
            InventoryCacheService.invalidate_inventory_cache(tenant_id)
            
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating raw material stock: {str(e)}")
            return False
    
    @staticmethod
    @cache_result(timeout='short', key_prefix='stock_movement_history')
    def get_stock_movement_history(tenant_id: str, item_type: str = 'all', days: int = 30) -> List[Dict]:
        """Get stock movement history dengan caching"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            movements = []
            
            # Get sales data (stock out)
            sales = Sale.query.filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).all()
            
            for sale in sales:
                for sale_item in sale.items:
                    if item_type == 'all' or item_type == 'product':
                        movements.append({
                            'date': sale.sale_date.isoformat(),
                            'type': 'sale',
                            'item_type': 'product',
                            'item_id': sale_item.product.id,
                            'item_name': sale_item.product.name,
                            'quantity': -sale_item.quantity,  # Negative for outgoing
                            'reference': f"Sale #{sale.id}",
                            'user': sale.user.username if sale.user else 'System'
                        })
            
            # Sort by date (newest first)
            movements.sort(key=lambda x: x['date'], reverse=True)
            
            return movements
            
        except Exception as e:
            current_app.logger.error(f"Error getting stock movement history: {str(e)}")
            return []
    
    @staticmethod
    def get_inventory_valuation(tenant_id: str) -> Dict:
        """Get inventory valuation dengan caching"""
        try:
            cache_key = f"inventory_valuation:tenant:{tenant_id}"
            cached_data = InventoryCacheService.get_cache(cache_key)
            if cached_data:
                return cached_data
            
            valuation = {
                'products': {
                    'total_quantity': 0,
                    'total_cost_value': 0.0,
                    'total_selling_value': 0.0,
                    'items': []
                },
                'raw_materials': {
                    'total_quantity': 0,
                    'total_cost_value': 0.0,
                    'items': []
                },
                'grand_total_cost': 0.0,
                'grand_total_selling': 0.0,
                'potential_profit': 0.0
            }
            
            # Calculate product valuation
            products = Product.query.filter_by(tenant_id=tenant_id).all()
            for product in products:
                if product.requires_stock_tracking and product.stock_quantity > 0:
                    cost_value = product.stock_quantity * float(product.cost_price or 0)
                    selling_value = product.stock_quantity * float(product.selling_price)
                    
                    valuation['products']['items'].append({
                        'id': product.id,
                        'name': product.name,
                        'quantity': product.stock_quantity,
                        'cost_price': float(product.cost_price or 0),
                        'selling_price': float(product.selling_price),
                        'cost_value': cost_value,
                        'selling_value': selling_value,
                        'potential_profit': selling_value - cost_value
                    })
                    
                    valuation['products']['total_quantity'] += product.stock_quantity
                    valuation['products']['total_cost_value'] += cost_value
                    valuation['products']['total_selling_value'] += selling_value
            
            # Calculate raw material valuation
            raw_materials = RawMaterial.query.filter_by(tenant_id=tenant_id).all()
            for raw_material in raw_materials:
                if raw_material.stock_quantity > 0:
                    cost_value = raw_material.stock_quantity * float(raw_material.cost_price)
                    
                    valuation['raw_materials']['items'].append({
                        'id': raw_material.id,
                        'name': raw_material.name,
                        'quantity': raw_material.stock_quantity,
                        'cost_price': float(raw_material.cost_price),
                        'unit': raw_material.unit,
                        'cost_value': cost_value
                    })
                    
                    valuation['raw_materials']['total_quantity'] += raw_material.stock_quantity
                    valuation['raw_materials']['total_cost_value'] += cost_value
            
            # Calculate totals
            valuation['grand_total_cost'] = (
                valuation['products']['total_cost_value'] + 
                valuation['raw_materials']['total_cost_value']
            )
            valuation['grand_total_selling'] = valuation['products']['total_selling_value']
            valuation['potential_profit'] = (
                valuation['grand_total_selling'] - valuation['grand_total_cost']
            )
            
            # Cache the result
            InventoryCacheService.set_cache(cache_key, valuation, 'medium')
            
            return valuation
            
        except Exception as e:
            current_app.logger.error(f"Error calculating inventory valuation: {str(e)}")
            return {'error': str(e)}