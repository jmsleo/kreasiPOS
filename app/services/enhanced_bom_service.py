"""
Enhanced BOM Service dengan Redis Cache Integration
Mengoptimalkan BOM calculations dan availability checks dengan caching
"""
from typing import Dict, List, Optional, Tuple
from flask import current_app
from app.models import Product, RawMaterial, BOMHeader, BOMItem
from app.extensions import db
from app.services.cache_service import BOMCacheService, cache_result
from datetime import datetime
import json


class EnhancedBOMService:
    """Enhanced BOM service dengan Redis caching untuk optimasi performa"""
    
    @staticmethod
    def create_or_update_bom(product_id: str, bom_items: List[Dict], tenant_id: str, notes: str = None) -> Dict:
        """Create atau update BOM dengan cache invalidation"""
        try:
            # Validate product exists
            product = Product.query.filter_by(id=product_id, tenant_id=tenant_id).first()
            if not product:
                return {'success': False, 'error': 'Product not found'}
            
            # Deactivate existing BOM
            existing_bom = BOMHeader.query.filter_by(
                product_id=product_id,
                is_active=True
            ).first()
            
            if existing_bom:
                existing_bom.is_active = False
            
            # Create new BOM header
            new_version = 1
            if existing_bom:
                new_version = existing_bom.version + 1
            
            bom_header = BOMHeader(
                product_id=product_id,
                version=new_version,
                is_active=True,
                notes=notes,
                created_at=datetime.utcnow()
            )
            
            db.session.add(bom_header)
            db.session.flush()  # Get BOM header ID
            
            # Add BOM items
            total_cost = 0.0
            for item_data in bom_items:
                raw_material = RawMaterial.query.filter_by(
                    id=item_data['raw_material_id'],
                    tenant_id=tenant_id
                ).first()
                
                if not raw_material:
                    db.session.rollback()
                    return {'success': False, 'error': f'Raw material {item_data["raw_material_id"]} not found'}
                
                bom_item = BOMItem(
                    bom_header_id=bom_header.id,
                    raw_material_id=item_data['raw_material_id'],
                    quantity=item_data['quantity'],
                    unit=item_data.get('unit', raw_material.unit)
                )
                
                db.session.add(bom_item)
                total_cost += item_data['quantity'] * float(raw_material.cost_price)
            
            # Update product BOM info
            product.has_bom = True
            product.bom_cost = total_cost
            
            db.session.commit()
            
            # Invalidate cache
            BOMCacheService.invalidate_bom_cache(product_id, tenant_id)
            
            return {
                'success': True,
                'bom_header_id': bom_header.id,
                'version': new_version,
                'total_cost': total_cost
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating/updating BOM: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_bom_details(product_id: str, tenant_id: str) -> Optional[Dict]:
        """Get BOM details dengan caching"""
        try:
            # Check cache first
            cache_key = f"bom_details:{product_id}:tenant:{tenant_id}"
            cached_data = BOMCacheService.get_cache(cache_key)
            if cached_data:
                return cached_data
            
            # Get active BOM
            bom_header = BOMHeader.query.filter_by(
                product_id=product_id,
                is_active=True
            ).first()
            
            if not bom_header:
                return None
            
            # Build BOM details
            bom_details = {
                'id': bom_header.id,
                'product_id': product_id,
                'version': bom_header.version,
                'notes': bom_header.notes,
                'created_at': bom_header.created_at.isoformat(),
                'items': [],
                'total_cost': 0.0,
                'total_items': 0
            }
            
            for bom_item in bom_header.items:
                raw_material = bom_item.raw_material
                item_cost = bom_item.quantity * float(raw_material.cost_price)
                
                item_details = {
                    'id': bom_item.id,
                    'raw_material_id': raw_material.id,
                    'raw_material_name': raw_material.name,
                    'raw_material_sku': raw_material.sku,
                    'quantity': bom_item.quantity,
                    'unit': bom_item.unit,
                    'cost_price': float(raw_material.cost_price),
                    'item_cost': item_cost,
                    'available_stock': raw_material.stock_quantity
                }
                
                bom_details['items'].append(item_details)
                bom_details['total_cost'] += item_cost
                bom_details['total_items'] += 1
            
            # Cache the result
            BOMCacheService.set_cache(cache_key, bom_details, 'medium')
            
            return bom_details
            
        except Exception as e:
            current_app.logger.error(f"Error getting BOM details: {str(e)}")
            return None
    
    @staticmethod
    def calculate_bom_requirements(product_id: str, quantity: int, tenant_id: str) -> Dict:
        """Calculate BOM requirements untuk quantity tertentu dengan caching"""
        try:
            # Log the parameters for debugging
            current_app.logger.info(f"Calculating BOM requirements - Product: {product_id}, Quantity: {quantity}, Tenant: {tenant_id}")
            
            # Check cache first
            cached_calc = BOMCacheService.get_cached_bom_calculation(product_id, tenant_id, quantity)
            if cached_calc:
                current_app.logger.info(f"Using cached BOM calculation for product {product_id}")
                return cached_calc
            
            bom_details = EnhancedBOMService.get_bom_details(product_id, tenant_id)
            if not bom_details:
                current_app.logger.warning(f"No active BOM found for product {product_id}")
                return {'success': False, 'error': 'No active BOM found'}
            
            requirements = {
                'product_id': product_id,
                'quantity': quantity,
                'total_cost': bom_details['total_cost'] * quantity,
                'requirements': [],
                'availability_status': 'available',
                'missing_items': []
            }
            
            for item in bom_details['items']:
                required_quantity = item['quantity'] * quantity
                available_stock = item['available_stock']
                is_sufficient = available_stock >= required_quantity
                
                current_app.logger.info(f"BOM Item: {item['raw_material_name']} - Required: {required_quantity}, Available: {available_stock}, Sufficient: {is_sufficient}")
                
                requirement = {
                    'raw_material_id': item['raw_material_id'],
                    'raw_material_name': item['raw_material_name'],
                    'required_quantity': required_quantity,
                    'available_stock': available_stock,
                    'unit': item['unit'],
                    'cost_per_unit': item['cost_price'],
                    'total_cost': required_quantity * item['cost_price'],
                    'is_sufficient': is_sufficient,
                    'shortage': max(0, required_quantity - available_stock)
                }
                
                requirements['requirements'].append(requirement)
                
                if not is_sufficient:
                    requirements['availability_status'] = 'insufficient'
                    requirements['missing_items'].append({
                        'name': item['raw_material_name'],
                        'shortage': requirement['shortage'],
                        'unit': item['unit']
                    })
            
            # Cache the calculation
            BOMCacheService.cache_bom_calculation(product_id, tenant_id, quantity, requirements)
            
            current_app.logger.info(f"BOM calculation completed - Status: {requirements['availability_status']}")
            return requirements
            
        except Exception as e:
            current_app.logger.error(f"Error calculating BOM requirements: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def validate_bom_availability(product_id: str, quantity: int, tenant_id: str) -> Dict:
        """Validate BOM availability dengan caching - FIXED PARAMETER ORDER"""
        try:
            current_app.logger.info(f"Validating BOM availability - Product: {product_id}, Quantity: {quantity}, Tenant: {tenant_id}")
            
            # Check cache first
            cached_availability = BOMCacheService.get_cached_bom_availability(product_id, tenant_id)
            if cached_availability and cached_availability.get('quantity') == quantity:
                current_app.logger.info(f"Using cached BOM availability for product {product_id}")
                return cached_availability
            
            # FIXED: Correct parameter order
            requirements = EnhancedBOMService.calculate_bom_requirements(product_id, quantity, tenant_id)
            
            if not requirements.get('success', True):
                current_app.logger.error(f"BOM requirements calculation failed: {requirements}")
                return requirements
            
            validation_result = {
                'product_id': product_id,
                'quantity': quantity,
                'is_available': requirements['availability_status'] == 'available',
                'total_cost': requirements['total_cost'],
                'validation_details': [],
                'missing_items': requirements.get('missing_items', [])
            }
            
            for req in requirements['requirements']:
                validation_result['validation_details'].append({
                    'raw_material_name': req['raw_material_name'],
                    'required': req['required_quantity'],
                    'available': req['available_stock'],
                    'sufficient': req['is_sufficient'],
                    'unit': req['unit']
                })
            
            # Cache the availability check
            BOMCacheService.cache_bom_availability(product_id, tenant_id, validation_result)
            
            current_app.logger.info(f"BOM validation completed - Available: {validation_result['is_available']}")
            if not validation_result['is_available']:
                current_app.logger.warning(f"BOM validation failed for product {product_id} - Missing items: {validation_result['missing_items']}")
            
            return validation_result
            
        except Exception as e:
            current_app.logger.error(f"Error validating BOM availability: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def process_bom_production(product_id: str, quantity: int, tenant_id: str) -> Dict:
        """Process BOM production (deduct raw materials, add finished product)"""
        try:
            current_app.logger.info(f"Processing BOM production - Product: {product_id}, Quantity: {quantity}")
            
            # Validate availability first
            validation = EnhancedBOMService.validate_bom_availability(product_id, quantity, tenant_id)
            if not validation['is_available']:
                current_app.logger.warning(f"BOM production failed - insufficient materials: {validation}")
                return {'success': False, 'error': 'Insufficient raw materials', 'details': validation}
            
            # Get BOM requirements
            requirements = EnhancedBOMService.calculate_bom_requirements(product_id, quantity, tenant_id)
            
            # Start transaction
            db.session.begin()
            
            # Deduct raw materials
            for req in requirements['requirements']:
                raw_material = RawMaterial.query.filter_by(
                    id=req['raw_material_id'],
                    tenant_id=tenant_id
                ).first()
                
                if raw_material:
                    current_app.logger.info(f"Deducting {req['required_quantity']} {req['unit']} of {raw_material.name}")
                    raw_material.stock_quantity -= req['required_quantity']
                    if raw_material.stock_quantity < 0:
                        db.session.rollback()
                        current_app.logger.error(f"Insufficient stock for {raw_material.name} after deduction")
                        return {'success': False, 'error': f'Insufficient stock for {raw_material.name}'}
            
            # Add finished product to inventory
            product = Product.query.filter_by(id=product_id, tenant_id=tenant_id).first()
            if product and product.requires_stock_tracking:
                product.stock_quantity += quantity
                current_app.logger.info(f"Added {quantity} units to product {product.name} inventory")
            
            # Commit transaction
            db.session.commit()
            
            # Invalidate caches
            BOMCacheService.invalidate_bom_cache(product_id, tenant_id)
            
            current_app.logger.info(f"BOM production completed successfully for {quantity} units of product {product_id}")
            
            return {
                'success': True,
                'produced_quantity': quantity,
                'total_cost': requirements['total_cost'],
                'raw_materials_used': len(requirements['requirements'])
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing BOM production: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    @cache_result(timeout='medium', key_prefix='bom_cost_analysis')
    def get_bom_cost_analysis(tenant_id: str) -> Dict:
        """Get BOM cost analysis untuk semua products dengan caching"""
        try:
            analysis = {
                'total_products_with_bom': 0,
                'total_bom_value': 0.0,
                'products': [],
                'cost_breakdown': {
                    'raw_materials_cost': 0.0,
                    'potential_profit_margin': 0.0
                }
            }
            
            # Get all products with BOM
            products_with_bom = Product.query.filter_by(
                tenant_id=tenant_id,
                has_bom=True
            ).all()
            
            for product in products_with_bom:
                bom_details = EnhancedBOMService.get_bom_details(product.id, tenant_id)
                if bom_details:
                    selling_price = float(product.selling_price)
                    bom_cost = bom_details['total_cost']
                    profit_margin = selling_price - bom_cost
                    profit_percentage = (profit_margin / selling_price * 100) if selling_price > 0 else 0
                    
                    product_analysis = {
                        'id': product.id,
                        'name': product.name,
                        'sku': product.sku,
                        'selling_price': selling_price,
                        'bom_cost': bom_cost,
                        'profit_margin': profit_margin,
                        'profit_percentage': profit_percentage,
                        'stock_quantity': product.stock_quantity,
                        'total_inventory_value': product.stock_quantity * selling_price,
                        'total_bom_cost_value': product.stock_quantity * bom_cost
                    }
                    
                    analysis['products'].append(product_analysis)
                    analysis['total_bom_value'] += product_analysis['total_bom_cost_value']
                    analysis['cost_breakdown']['raw_materials_cost'] += bom_cost
            
            analysis['total_products_with_bom'] = len(analysis['products'])
            
            # Calculate overall profit margin
            total_selling_value = sum(p['total_inventory_value'] for p in analysis['products'])
            if total_selling_value > 0:
                analysis['cost_breakdown']['potential_profit_margin'] = (
                    (total_selling_value - analysis['total_bom_value']) / total_selling_value * 100
                )
            
            return analysis
            
        except Exception as e:
            current_app.logger.error(f"Error getting BOM cost analysis: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def delete_bom(product_id: str, tenant_id: str) -> Dict:
        """Delete BOM dengan cache invalidation"""
        try:
            # Find active BOM
            bom_header = BOMHeader.query.filter_by(
                product_id=product_id,
                is_active=True
            ).first()
            
            if not bom_header:
                return {'success': False, 'error': 'No active BOM found'}
            
            # Delete BOM items first
            BOMItem.query.filter_by(bom_header_id=bom_header.id).delete()
            
            # Delete BOM header
            db.session.delete(bom_header)
            
            # Update product
            product = Product.query.filter_by(id=product_id, tenant_id=tenant_id).first()
            if product:
                product.has_bom = False
                product.bom_cost = 0.0
            
            db.session.commit()
            
            # Invalidate cache
            BOMCacheService.invalidate_bom_cache(product_id, tenant_id)
            
            return {'success': True, 'message': 'BOM deleted successfully'}
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting BOM: {str(e)}")
            return {'success': False, 'error': str(e)}