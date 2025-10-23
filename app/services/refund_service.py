from app import db
from app.models import Sale, SaleItem, Refund, RefundItem, RefundStatus, StockAdjustment
from flask import current_app
from flask_login import current_user
from typing import List, Dict, Any, Tuple
import uuid
from datetime import datetime

class RefundService:
    """Service class for Refund operations"""
    
    @staticmethod
    def create_refund(sale_id: str, refund_items: List[Dict], refund_reason: str = None, 
                     notes: str = None, user_id: str = None) -> Refund:
        """
        Create a new refund
        
        Args:
            sale_id (str): Original sale ID
            refund_items (List[Dict]): List of items to refund with quantities
            refund_reason (str): Reason for refund
            notes (str): Additional notes
            user_id (str): User processing the refund
            
        Returns:
            Refund: Created refund object
        """
        try:
            # Validate sale exists and can be refunded
            sale = Sale.query.get(sale_id)
            if not sale:
                raise ValueError("Sale not found")
            
            if not sale.can_be_refunded():
                raise ValueError("Sale cannot be refunded")
            
            # Validate refund items
            total_refund_amount = 0.0
            validated_items = []
            
            for item_data in refund_items:
                sale_item = SaleItem.query.get(item_data['sale_item_id'])
                if not sale_item or sale_item.sale_id != sale_id:
                    raise ValueError(f"Sale item {item_data['sale_item_id']} not found in this sale")
                
                refund_quantity = int(item_data['quantity'])
                if refund_quantity <= 0:
                    raise ValueError("Refund quantity must be positive")
                
                if refund_quantity > sale_item.get_refundable_quantity():
                    raise ValueError(f"Cannot refund {refund_quantity} of {sale_item.product.name}. "
                                   f"Only {sale_item.get_refundable_quantity()} available for refund")
                
                # Calculate refund amount for this item
                item_refund_amount = sale_item.unit_price * refund_quantity
                total_refund_amount += item_refund_amount
                
                validated_items.append({
                    'sale_item': sale_item,
                    'quantity': refund_quantity,
                    'unit_price': sale_item.unit_price,
                    'total_price': item_refund_amount
                })
            
            if not validated_items:
                raise ValueError("No valid items to refund")
            
            # Check if total refund amount doesn't exceed refundable amount
            if total_refund_amount > sale.get_refundable_amount():
                raise ValueError(f"Refund amount ({total_refund_amount}) exceeds refundable amount ({sale.get_refundable_amount()})")
            
            # Generate refund number
            refund_number = RefundService._generate_refund_number(sale.tenant_id)
            
            # Create refund record
            refund = Refund(
                tenant_id=sale.tenant_id,
                refund_number=refund_number,
                original_sale_id=sale_id,
                refund_amount=total_refund_amount,
                refund_reason=refund_reason,
                notes=notes,
                processed_by=user_id,
                status=RefundStatus.PENDING
            )
            
            db.session.add(refund)
            db.session.flush()  # Get refund ID
            
            # Create refund items
            for item_data in validated_items:
                refund_item = RefundItem(
                    refund_id=refund.id,
                    original_sale_item_id=item_data['sale_item'].id,
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    total_price=item_data['total_price']
                )
                db.session.add(refund_item)
            
            db.session.commit()
            
            current_app.logger.info(f"Refund created: {refund_number} for sale {sale.receipt_number}")
            return refund
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating refund: {str(e)}")
            raise
    
    @staticmethod
    def _generate_refund_number(tenant_id: str) -> str:
        """
        Generate unique refund number
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            str: Generated refund number
        """
        try:
            # Format: RF-YYYYMMDD-XXXXXX
            date_str = datetime.now().strftime('%Y%m%d')
            base_number = f"RF-{date_str}"
            
            # Find the next sequence number for today
            existing_count = Refund.query.filter(
                Refund.tenant_id == tenant_id,
                Refund.refund_number.like(f"{base_number}-%")
            ).count()
            
            sequence = existing_count + 1
            return f"{base_number}-{sequence:06d}"
            
        except Exception as e:
            current_app.logger.error(f"Error generating refund number: {str(e)}")
            # Fallback to UUID-based number
            return f"RF-{str(uuid.uuid4())[:8].upper()}"
    
    @staticmethod
    def process_refund(refund_id: str, user_id: str = None) -> Refund:
        """
        Process a pending refund and restore inventory
        
        Args:
            refund_id (str): Refund ID
            user_id (str): User processing the refund
            
        Returns:
            Refund: Processed refund object
        """
        try:
            refund = Refund.query.get(refund_id)
            if not refund:
                raise ValueError("Refund not found")
            
            if refund.status != RefundStatus.PENDING:
                raise ValueError(f"Refund is already {refund.status.value}")
            
            # Process inventory restoration
            for refund_item in refund.items:
                sale_item = refund_item.original_sale_item
                product = sale_item.product
                
                current_app.logger.info(f"Processing refund for {product.name}, quantity: {refund_item.quantity}")
                
                # Restore inventory based on product type
                if product.requires_stock_tracking and not product.has_bom:
                    # Restore regular product stock
                    product.stock_quantity += refund_item.quantity
                    current_app.logger.info(f"Restored product stock: {product.name} +{refund_item.quantity}")
                    
                elif product.has_bom:
                    # Restore raw materials based on BOM
                    active_bom = product.get_active_bom()
                    if active_bom:
                        for bom_item in active_bom.items:
                            if bom_item.raw_material:
                                # Calculate quantity to restore
                                restore_quantity = bom_item.quantity * refund_item.quantity
                                original_stock = bom_item.raw_material.stock_quantity
                                
                                # Update raw material stock
                                bom_item.raw_material.update_stock(restore_quantity)
                                
                                current_app.logger.info(f"Restored raw material: {bom_item.raw_material.name} "
                                                       f"+{restore_quantity} (from {original_stock} to {bom_item.raw_material.stock_quantity})")
                                
                                # Create stock adjustment record
                                if user_id:
                                    from app.services.raw_material_service import RawMaterialService
                                    RawMaterialService._create_stock_adjustment(
                                        raw_material_id=bom_item.raw_material.id,
                                        user_id=user_id,
                                        adjustment_type='refund',
                                        quantity_before=original_stock,
                                        quantity_after=bom_item.raw_material.stock_quantity,
                                        quantity_changed=restore_quantity,
                                        reason=f'Refund: {refund.refund_number}',
                                        notes=f'Restored from product refund: {product.name} x{refund_item.quantity}'
                                    )
            
            # Update refund status
            refund.status = RefundStatus.COMPLETED
            refund.processed_at = datetime.utcnow()
            if user_id:
                refund.processed_by = user_id
            
            db.session.commit()
            
            current_app.logger.info(f"Refund processed successfully: {refund.refund_number}")
            return refund
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing refund: {str(e)}")
            raise
    
    @staticmethod
    def cancel_refund(refund_id: str, user_id: str = None) -> Refund:
        """
        Cancel a pending refund
        
        Args:
            refund_id (str): Refund ID
            user_id (str): User cancelling the refund
            
        Returns:
            Refund: Cancelled refund object
        """
        try:
            refund = Refund.query.get(refund_id)
            if not refund:
                raise ValueError("Refund not found")
            
            if refund.status != RefundStatus.PENDING:
                raise ValueError(f"Cannot cancel refund with status: {refund.status.value}")
            
            refund.status = RefundStatus.CANCELLED
            refund.processed_at = datetime.utcnow()
            if user_id:
                refund.processed_by = user_id
            
            db.session.commit()
            
            current_app.logger.info(f"Refund cancelled: {refund.refund_number}")
            return refund
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cancelling refund: {str(e)}")
            raise
    
    @staticmethod
    def get_refunds_by_tenant(tenant_id: str, status: RefundStatus = None, 
                             page: int = 1, per_page: int = 20) -> Any:
        """
        Get refunds for a tenant with pagination
        
        Args:
            tenant_id (str): Tenant ID
            status (RefundStatus): Filter by status
            page (int): Page number
            per_page (int): Items per page
            
        Returns:
            Pagination: Paginated refunds
        """
        try:
            query = Refund.query.filter_by(tenant_id=tenant_id)
            
            if status:
                query = query.filter_by(status=status)
            
            return query.order_by(Refund.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
        except Exception as e:
            current_app.logger.error(f"Error getting refunds: {str(e)}")
            return None
    
    @staticmethod
    def get_refund_by_number(tenant_id: str, refund_number: str) -> Refund:
        """
        Get refund by refund number
        
        Args:
            tenant_id (str): Tenant ID
            refund_number (str): Refund number
            
        Returns:
            Refund: Refund object or None
        """
        try:
            return Refund.query.filter_by(
                tenant_id=tenant_id,
                refund_number=refund_number
            ).first()
            
        except Exception as e:
            current_app.logger.error(f"Error getting refund by number: {str(e)}")
            return None
    
    @staticmethod
    def get_refundable_sales(tenant_id: str, days_limit: int = 30, 
                           page: int = 1, per_page: int = 20) -> Any:
        """
        Get sales that can be refunded
        
        Args:
            tenant_id (str): Tenant ID
            days_limit (int): Number of days to look back for refundable sales
            page (int): Page number
            per_page (int): Items per page
            
        Returns:
            Pagination: Paginated refundable sales
        """
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_limit)
            
            # Get sales that have refundable amount > 0 and are within the time limit
            query = Sale.query.filter(
                Sale.tenant_id == tenant_id,
                Sale.payment_status == 'completed',
                Sale.created_at >= cutoff_date
            )
            
            # Filter sales that still have refundable amount
            refundable_sales = []
            for sale in query.all():
                if sale.can_be_refunded():
                    refundable_sales.append(sale)
            
            # Manual pagination since we filtered after query
            start = (page - 1) * per_page
            end = start + per_page
            paginated_sales = refundable_sales[start:end]
            
            # Create a simple pagination-like object
            class SimplePagination:
                def __init__(self, items, page, per_page, total):
                    self.items = items
                    self.page = page
                    self.per_page = per_page
                    self.total = total
                    self.pages = (total + per_page - 1) // per_page
                    self.has_prev = page > 1
                    self.has_next = page < self.pages
                    self.prev_num = page - 1 if self.has_prev else None
                    self.next_num = page + 1 if self.has_next else None
            
            return SimplePagination(paginated_sales, page, per_page, len(refundable_sales))
            
        except Exception as e:
            current_app.logger.error(f"Error getting refundable sales: {str(e)}")
            return None
    
    @staticmethod
    def validate_refund_request(sale_id: str, refund_items: List[Dict]) -> Tuple[bool, str]:
        """
        Validate a refund request before processing
        
        Args:
            sale_id (str): Sale ID
            refund_items (List[Dict]): Items to refund
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        try:
            sale = Sale.query.get(sale_id)
            if not sale:
                return False, "Sale not found"
            
            if not sale.can_be_refunded():
                return False, "Sale cannot be refunded"
            
            total_refund_amount = 0.0
            
            for item_data in refund_items:
                sale_item = SaleItem.query.get(item_data.get('sale_item_id'))
                if not sale_item or sale_item.sale_id != sale_id:
                    return False, f"Invalid sale item: {item_data.get('sale_item_id')}"
                
                refund_quantity = item_data.get('quantity', 0)
                if refund_quantity <= 0:
                    return False, f"Invalid quantity for {sale_item.product.name}"
                
                if refund_quantity > sale_item.get_refundable_quantity():
                    return False, f"Cannot refund {refund_quantity} of {sale_item.product.name}. " \
                                 f"Only {sale_item.get_refundable_quantity()} available"
                
                total_refund_amount += sale_item.unit_price * refund_quantity
            
            if total_refund_amount > sale.get_refundable_amount():
                return False, f"Refund amount exceeds refundable amount"
            
            return True, "Valid refund request"
            
        except Exception as e:
            current_app.logger.error(f"Error validating refund request: {str(e)}")
            return False, str(e)
    
    @staticmethod
    def get_refund_statistics(tenant_id: str, start_date: datetime = None, 
                            end_date: datetime = None) -> Dict[str, Any]:
        """
        Get refund statistics for reporting
        
        Args:
            tenant_id (str): Tenant ID
            start_date (datetime): Start date for statistics
            end_date (datetime): End date for statistics
            
        Returns:
            Dict[str, Any]: Refund statistics
        """
        try:
            query = Refund.query.filter_by(tenant_id=tenant_id)
            
            if start_date:
                query = query.filter(Refund.created_at >= start_date)
            if end_date:
                query = query.filter(Refund.created_at <= end_date)
            
            refunds = query.all()
            
            stats = {
                'total_refunds': len(refunds),
                'total_refund_amount': sum(r.refund_amount for r in refunds if r.status == RefundStatus.COMPLETED),
                'pending_refunds': len([r for r in refunds if r.status == RefundStatus.PENDING]),
                'completed_refunds': len([r for r in refunds if r.status == RefundStatus.COMPLETED]),
                'cancelled_refunds': len([r for r in refunds if r.status == RefundStatus.CANCELLED]),
                'refunds_by_reason': {}
            }
            
            # Group by reason
            for refund in refunds:
                reason = refund.refund_reason or 'No reason specified'
                if reason not in stats['refunds_by_reason']:
                    stats['refunds_by_reason'][reason] = {
                        'count': 0,
                        'total_amount': 0.0
                    }
                stats['refunds_by_reason'][reason]['count'] += 1
                if refund.status == RefundStatus.COMPLETED:
                    stats['refunds_by_reason'][reason]['total_amount'] += refund.refund_amount
            
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Error getting refund statistics: {str(e)}")
            return {
                'total_refunds': 0,
                'total_refund_amount': 0.0,
                'pending_refunds': 0,
                'completed_refunds': 0,
                'cancelled_refunds': 0,
                'refunds_by_reason': {}
            }