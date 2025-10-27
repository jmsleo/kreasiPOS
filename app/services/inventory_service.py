from app import db
from app.models import Product, RawMaterial, RestockOrder, MarketplaceItem, Sale, SaleItem
from app.services.bom_service import BOMService
from app.services.enhanced_bom_service import EnhancedBOMService
from app.services.raw_material_service import RawMaterialService
from flask import current_app

class InventoryService:
    """Service class for coordinating inventory operations across models"""
    
    @staticmethod
    def process_marketplace_purchase(restock_order):
        """
        Process marketplace purchase and update appropriate inventory
        
        Args:
            restock_order (RestockOrder): Verified restock order
            
        Returns:
            bool: Success status
        """
        try:
            marketplace_item = restock_order.marketplace_item
            
            if marketplace_item.item_type == 'product':
                # Add to Product inventory
                return InventoryService._add_product_stock(
                    marketplace_item, 
                    restock_order.quantity, 
                    restock_order.tenant_id
                )
            elif marketplace_item.item_type == 'raw_material':
                # Add to Raw Material inventory
                return InventoryService._add_raw_material_stock(
                    marketplace_item, 
                    restock_order.quantity, 
                    restock_order.tenant_id
                )
            else:
                raise ValueError(f"Unknown item type: {marketplace_item.item_type}")
                
        except Exception as e:
            current_app.logger.error(f"Error processing marketplace purchase: {str(e)}")
            raise
    
    @staticmethod
    def _add_product_stock(marketplace_item, quantity, tenant_id):
        """
        Add stock to product inventory from marketplace purchase
        
        Args:
            marketplace_item (MarketplaceItem): Marketplace item
            quantity (int): Quantity purchased
            tenant_id (str): Tenant ID
            
        Returns:
            bool: Success status
        """
        try:
            # Find or create product based on marketplace item
            product = Product.query.filter_by(
                tenant_id=tenant_id,
                name=marketplace_item.name
            ).first()
            
            if not product:
                # Create new product from marketplace item
                product = Product(
                    tenant_id=tenant_id,
                    name=marketplace_item.name,
                    description=marketplace_item.description,
                    price=marketplace_item.price * 1.2,  # Add 20% markup
                    cost_price=marketplace_item.price,
                    stock_quantity=quantity,
                    sku=marketplace_item.sku,
                    image_url=marketplace_item.image_url
                )
                db.session.add(product)
            else:
                # Update existing product stock
                product.stock_quantity += quantity
                # Update cost price if different
                if product.cost_price != marketplace_item.price:
                    product.cost_price = marketplace_item.price
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding product stock: {str(e)}")
            raise
    
    @staticmethod
    def _add_raw_material_stock(marketplace_item, quantity, tenant_id):
        """
        Add stock to raw material inventory from marketplace purchase
        
        Args:
            marketplace_item (MarketplaceItem): Marketplace item
            quantity (int): Quantity purchased
            tenant_id (str): Tenant ID
            
        Returns:
            bool: Success status
        """
        try:
            # Find or create raw material based on marketplace item
            raw_material = RawMaterial.query.filter_by(
                tenant_id=tenant_id,
                name=marketplace_item.name
            ).first()
            
            if not raw_material:
                # Create new raw material from marketplace item
                raw_material = RawMaterial(
                    tenant_id=tenant_id,
                    name=marketplace_item.name,
                    description=marketplace_item.description,
                    cost_price=marketplace_item.price,
                    stock_quantity=quantity,
                    sku=marketplace_item.sku
                )
                db.session.add(raw_material)
            else:
                # Update existing raw material stock
                raw_material.stock_quantity += quantity
                # Update cost price if different
                if raw_material.cost_price != marketplace_item.price:
                    raw_material.cost_price = marketplace_item.price
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding raw material stock: {str(e)}")
            raise
    
    @staticmethod
    def process_sale_deduction(sale):
        """
        Process inventory deduction for a sale (both regular stock and BOM)
        
        Args:
            sale (Sale): Sale object with items
            
        Returns:
            bool: Success status
        """
        try:
            for sale_item in sale.items:
                product = sale_item.product
                
                # Handle regular stock tracking
                if product.requires_stock_tracking:
                    if product.stock_quantity < sale_item.quantity:
                        raise ValueError(f"Insufficient stock for {product.name}")
                    product.stock_quantity -= sale_item.quantity
                
                # Handle BOM deduction using enhanced service
                if product.has_bom:
                    # Use enhanced BOM service with correct parameter order
                    bom_validation = EnhancedBOMService.validate_bom_availability(
                        product.id, 
                        sale_item.quantity, 
                        sale.tenant_id
                    )
                    
                    if not bom_validation.get('is_available', False):
                        raise ValueError(f"Insufficient raw materials for {product.name}")
                    
                    # Process BOM production/deduction
                    bom_result = EnhancedBOMService.process_bom_production(
                        product.id, 
                        sale_item.quantity, 
                        sale.tenant_id
                    )
                    
                    if not bom_result.get('success', False):
                        raise ValueError(f"Failed to process BOM deduction for {product.name}: {bom_result.get('error')}")
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing sale deduction: {str(e)}")
            raise
    
    @staticmethod
    def get_inventory_status(tenant_id):
        """
        Get comprehensive inventory status for a tenant
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            dict: Inventory status summary
        """
        try:
            # Product inventory
            products = Product.query.filter_by(tenant_id=tenant_id, is_active=True).all()
            low_stock_products = [p for p in products if p.requires_stock_tracking and p.stock_quantity <= p.stock_alert]
            
            # Raw material inventory
            raw_materials = RawMaterial.query.filter_by(tenant_id=tenant_id, is_active=True).all()
            low_stock_materials = RawMaterialService.get_low_stock_materials(tenant_id)
            
            # BOM products
            bom_products = [p for p in products if p.has_bom]
            bom_availability_issues = []
            
            for product in bom_products:
                # Use enhanced BOM service for availability check
                bom_validation = EnhancedBOMService.validate_bom_availability(
                    product.id, 1, tenant_id
                )
                if not bom_validation.get('is_available', True):
                    bom_availability_issues.append(product)
            
            # Calculate total inventory value
            product_value = sum((p.stock_quantity * (p.cost_price or 0)) for p in products if p.requires_stock_tracking)
            raw_material_value = sum((rm.stock_quantity * (rm.cost_price or 0)) for rm in raw_materials)
            
            return {
                'products': {
                    'total': len(products),
                    'low_stock': len(low_stock_products),
                    'with_bom': len(bom_products),
                    'total_value': product_value
                },
                'raw_materials': {
                    'total': len(raw_materials),
                    'low_stock': len(low_stock_materials),
                    'total_value': raw_material_value
                },
                'alerts': {
                    'low_stock_products': low_stock_products,
                    'low_stock_materials': low_stock_materials,
                    'bom_availability_issues': bom_availability_issues
                },
                'total_inventory_value': product_value + raw_material_value
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting inventory status: {str(e)}")
            return {}
    
    @staticmethod
    def validate_sale_availability(sale_items_data, tenant_id):
        """
        Validate if all items in a sale are available
        
        Args:
            sale_items_data (list): List of dicts with product_id and quantity
            tenant_id (str): Tenant ID
            
        Returns:
            tuple: (bool, list) - (is_valid, validation_errors)
        """
        try:
            errors = []
            
            for item_data in sale_items_data:
                product = Product.query.filter_by(
                    id=item_data['product_id'],
                    tenant_id=tenant_id
                ).first()
                
                if not product:
                    errors.append(f"Product not found: {item_data['product_id']}")
                    continue
                
                quantity = item_data['quantity']
                
                # Check regular stock
                if product.requires_stock_tracking:
                    if product.stock_quantity < quantity:
                        errors.append(f"Insufficient stock for {product.name}: need {quantity}, have {product.stock_quantity}")
                
                # Check BOM availability using enhanced service
                if product.has_bom:
                    bom_validation = EnhancedBOMService.validate_bom_availability(
                        product.id, quantity, tenant_id
                    )
                    
                    if not bom_validation.get('is_available', False):
                        missing_items = bom_validation.get('missing_items', [])
                        if missing_items:
                            missing_names = [item['name'] for item in missing_items]
                            errors.append(f"BOM materials insufficient for {product.name}: {', '.join(missing_names)}")
                        else:
                            errors.append(f"BOM materials insufficient for {product.name}")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            current_app.logger.error(f"Error validating sale availability: {str(e)}")
            return False, [str(e)]
    
    @staticmethod
    def get_restock_recommendations(tenant_id):
        """
        Get restock recommendations based on low stock and BOM usage
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            dict: Restock recommendations
        """
        try:
            recommendations = {
                'products': [],
                'raw_materials': []
            }
            
            # Product recommendations
            low_stock_products = Product.query.filter(
                Product.tenant_id == tenant_id,
                Product.is_active == True,
                Product.requires_stock_tracking == True,
                Product.stock_quantity <= Product.stock_alert
            ).all()
            
            for product in low_stock_products:
                recommendations['products'].append({
                    'id': product.id,
                    'name': product.name,
                    'current_stock': product.stock_quantity,
                    'alert_level': product.stock_alert,
                    'suggested_restock': product.stock_alert * 2,
                    'estimated_cost': (product.stock_alert * 2) * (product.cost_price or 0)
                })
            
            # Raw material recommendations
            low_stock_materials = RawMaterialService.get_low_stock_materials(tenant_id)
            
            for material in low_stock_materials:
                recommendations['raw_materials'].append({
                    'id': material.id,
                    'name': material.name,
                    'current_stock': material.stock_quantity,
                    'alert_level': material.stock_alert,
                    'suggested_restock': material.stock_alert * 2,
                    'estimated_cost': (material.stock_alert * 2) * (material.cost_price or 0),
                    'unit': material.unit
                })
            
            return recommendations
            
        except Exception as e:
            current_app.logger.error(f"Error getting restock recommendations: {str(e)}")
            return {'products': [], 'raw_materials': []}