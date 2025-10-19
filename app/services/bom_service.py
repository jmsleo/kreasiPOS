from app import db
from app.models import BOMHeader, BOMItem, Product, RawMaterial
from flask import current_app

class BOMService:
    """Service class for BOM (Bill of Materials) operations"""
    
    @staticmethod
    def create_bom(product_id, items_data, notes=None):
        """
        Create a new BOM for a product
        
        Args:
            product_id (str): Product ID
            items_data (list): List of dicts with raw_material_id, quantity, unit
            notes (str): Optional notes
            
        Returns:
            BOMHeader: Created BOM header
        """
        try:
            # Deactivate existing BOMs for this product
            existing_boms = BOMHeader.query.filter_by(product_id=product_id, is_active=True).all()
            for bom in existing_boms:
                bom.is_active = False
            
            # Create new BOM header
            bom_header = BOMHeader(
                product_id=product_id,
                notes=notes,
                is_active=True
            )
            db.session.add(bom_header)
            db.session.flush()  # Get the ID
            
            # Create BOM items
            for item_data in items_data:
                bom_item = BOMItem(
                    bom_header_id=bom_header.id,
                    raw_material_id=item_data['raw_material_id'],
                    quantity=float(item_data['quantity']),
                    unit=item_data.get('unit', ''),
                    notes=item_data.get('notes', '')
                )
                db.session.add(bom_item)
            
            # Update product BOM status and cost
            product = Product.query.get(product_id)
            if product:
                product.has_bom = True
                product.calculate_bom_cost()
            
            db.session.commit()
            return bom_header
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating BOM: {str(e)}")
            raise
    
    @staticmethod
    def update_bom(bom_header_id, items_data, notes=None):
        """
        Update existing BOM
        
        Args:
            bom_header_id (str): BOM header ID
            items_data (list): List of dicts with raw_material_id, quantity, unit
            notes (str): Optional notes
            
        Returns:
            BOMHeader: Updated BOM header
        """
        try:
            bom_header = BOMHeader.query.get(bom_header_id)
            if not bom_header:
                raise ValueError("BOM not found")
            
            # Update notes
            if notes is not None:
                bom_header.notes = notes
            
            # Delete existing items
            BOMItem.query.filter_by(bom_header_id=bom_header_id).delete()
            
            # Create new items
            for item_data in items_data:
                bom_item = BOMItem(
                    bom_header_id=bom_header_id,
                    raw_material_id=item_data['raw_material_id'],
                    quantity=float(item_data['quantity']),
                    unit=item_data.get('unit', ''),
                    notes=item_data.get('notes', '')
                )
                db.session.add(bom_item)
            
            # Update product BOM cost
            if bom_header.product:
                bom_header.product.calculate_bom_cost()
            
            db.session.commit()
            return bom_header
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating BOM: {str(e)}")
            raise
    
    @staticmethod
    def delete_bom(bom_header_id):
        """
        Delete BOM and update product status
        
        Args:
            bom_header_id (str): BOM header ID
            
        Returns:
            bool: Success status
        """
        try:
            bom_header = BOMHeader.query.get(bom_header_id)
            if not bom_header:
                raise ValueError("BOM not found")
            
            product = bom_header.product
            
            # Delete BOM items first (cascade should handle this, but explicit is better)
            BOMItem.query.filter_by(bom_header_id=bom_header_id).delete()
            
            # Delete BOM header
            db.session.delete(bom_header)
            
            # Update product status if no other active BOMs
            if product:
                remaining_boms = BOMHeader.query.filter_by(product_id=product.id, is_active=True).count()
                if remaining_boms == 0:
                    product.has_bom = False
                    product.bom_cost = 0.0
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting BOM: {str(e)}")
            raise
    
    @staticmethod
    def validate_bom_availability(bom_header_id, quantity=1):
        """
        Validate if raw materials are available for BOM production
        
        Args:
            bom_header_id (str): BOM header ID
            quantity (int): Production quantity
            
        Returns:
            tuple: (bool, dict) - (is_valid, availability_details)
        """
        try:
            bom_header = BOMHeader.query.get(bom_header_id)
            if not bom_header:
                return False, {"error": "BOM not found"}
            
            availability = []
            total_cost = 0
            all_available = True
            
            for bom_item in bom_header.items:
                required_quantity = bom_item.quantity * quantity
                available_quantity = bom_item.raw_material.stock_quantity
                sufficient = available_quantity >= required_quantity
                
                if not sufficient:
                    all_available = False
                
                item_cost = (bom_item.quantity * (bom_item.raw_material.cost_price or 0)) * quantity
                total_cost += item_cost
                
                availability.append({
                    'raw_material_id': bom_item.raw_material_id,
                    'raw_material_name': bom_item.raw_material.name,
                    'required': required_quantity,
                    'available': available_quantity,
                    'sufficient': sufficient,
                    'unit': bom_item.unit,
                    'cost_per_unit': bom_item.raw_material.cost_price or 0,
                    'total_cost': item_cost
                })
            
            return all_available, {
                'valid': all_available,
                'total_cost': total_cost,
                'availability': availability
            }
            
        except Exception as e:
            current_app.logger.error(f"Error validating BOM availability: {str(e)}")
            return False, {"error": str(e)}
    
    @staticmethod
    def process_bom_deduction(bom_header_id, quantity=1):
        """
        Process raw material deduction based on BOM
        
        Args:
            bom_header_id (str): BOM header ID
            quantity (int): Production quantity
            
        Returns:
            bool: Success status
        """
        try:
            # First validate availability
            is_valid, details = BOMService.validate_bom_availability(bom_header_id, quantity)
            if not is_valid:
                raise ValueError(f"Insufficient raw materials: {details}")
            
            bom_header = BOMHeader.query.get(bom_header_id)
            if not bom_header:
                raise ValueError("BOM not found")
            
            # Process deductions
            for bom_item in bom_header.items:
                required_quantity = bom_item.quantity * quantity
                bom_item.raw_material.update_stock(-required_quantity)
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error processing BOM deduction: {str(e)}")
            raise
    
    @staticmethod
    def get_bom_by_product(product_id):
        """Get active BOM for a product - MODIFIED to allow multiple"""
        return BOMHeader.query.filter_by(
            product_id=product_id, 
            is_active=True
        ).first()  # Tetap first() jika ingin BOM aktif utama

    @staticmethod
    def get_all_boms_by_product(product_id):
        """Get all active BOMs for a product"""
        return BOMHeader.query.filter_by(
            product_id=product_id, 
            is_active=True
        ).all()
    
    @staticmethod
    def get_bom_cost_analysis(tenant_id):
        """
        Get BOM cost analysis for all products in tenant
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            list: List of products with BOM cost analysis
        """
        try:
            products = Product.query.filter_by(tenant_id=tenant_id, has_bom=True).all()
            analysis = []
            
            for product in products:
                active_bom = BOMService.get_bom_by_product(product.id)
                if active_bom:
                    bom_cost = active_bom.calculate_total_cost()
                    profit_margin = ((product.price - bom_cost) / product.price * 100) if product.price > 0 else 0
                    
                    analysis.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'selling_price': product.price,
                        'bom_cost': bom_cost,
                        'profit_amount': product.price - bom_cost,
                        'profit_margin': profit_margin,
                        'bom_items_count': active_bom.items.count()
                    })
            
            return analysis
            
        except Exception as e:
            current_app.logger.error(f"Error getting BOM cost analysis: {str(e)}")
            return []