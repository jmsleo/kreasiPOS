"""
Enhanced Dashboard Service dengan Redis Cache Integration
Mengoptimalkan dashboard statistics dan chart data dengan caching
"""
from typing import Dict, List, Optional
from flask import current_app
from app.models import Sale, Product, RawMaterial, Customer, SaleItem, User
from app.extensions import db
from app.services.cache_service import DashboardCacheService, cache_result
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
import json


class EnhancedDashboardService:
    """Enhanced dashboard service dengan Redis caching untuk performa optimal"""
    
    @staticmethod
    def get_dashboard_statistics(tenant_id: str, period: str = 'today') -> Dict:
        """Get dashboard statistics dengan caching berdasarkan period"""
        try:
            # Check cache first
            cached_stats = DashboardCacheService.get_cached_dashboard_stats(tenant_id, period)
            if cached_stats:
                return cached_stats
            
            # Calculate date range berdasarkan period
            end_date = datetime.utcnow()
            
            if period == 'today':
                start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'week':
                start_date = end_date - timedelta(days=7)
            elif period == 'month':
                start_date = end_date - timedelta(days=30)
            elif period == 'year':
                start_date = end_date - timedelta(days=365)
            else:
                start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Calculate statistics
            stats = {
                'period': period,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'sales': EnhancedDashboardService._get_sales_stats(tenant_id, start_date, end_date),
                'inventory': EnhancedDashboardService._get_inventory_stats(tenant_id),
                'customers': EnhancedDashboardService._get_customer_stats(tenant_id, start_date, end_date),
                'alerts': EnhancedDashboardService._get_alert_stats(tenant_id),
                'performance': EnhancedDashboardService._get_performance_stats(tenant_id, start_date, end_date)
            }
            
            # Cache the statistics
            DashboardCacheService.cache_dashboard_stats(tenant_id, period, stats)
            
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Error getting dashboard statistics: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _get_sales_stats(tenant_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get sales statistics untuk period tertentu"""
        try:
            # Total sales
            total_sales = db.session.query(func.sum(Sale.total_amount)).filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).scalar() or 0
            
            # Sales count
            sales_count = Sale.query.filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).count()
            
            # Average transaction value
            avg_transaction = float(total_sales) / sales_count if sales_count > 0 else 0
            
            # Compare dengan period sebelumnya untuk growth calculation
            period_duration = end_date - start_date
            prev_start = start_date - period_duration
            prev_end = start_date
            
            prev_total_sales = db.session.query(func.sum(Sale.total_amount)).filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= prev_start,
                Sale.sale_date <= prev_end
            ).scalar() or 0
            
            prev_sales_count = Sale.query.filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= prev_start,
                Sale.sale_date <= prev_end
            ).count()
            
            # Calculate growth percentages
            sales_growth = 0
            count_growth = 0
            
            if prev_total_sales > 0:
                sales_growth = ((float(total_sales) - float(prev_total_sales)) / float(prev_total_sales)) * 100
            
            if prev_sales_count > 0:
                count_growth = ((sales_count - prev_sales_count) / prev_sales_count) * 100
            
            return {
                'total_amount': float(total_sales),
                'transaction_count': sales_count,
                'average_transaction': avg_transaction,
                'sales_growth': round(sales_growth, 2),
                'count_growth': round(count_growth, 2),
                'previous_period': {
                    'total_amount': float(prev_total_sales),
                    'transaction_count': prev_sales_count
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Error calculating sales stats: {str(e)}")
            return {}
    
    @staticmethod
    def _get_inventory_stats(tenant_id: str) -> Dict:
        """Get inventory statistics"""
        try:
            # Product statistics
            products = Product.query.filter_by(tenant_id=tenant_id).all()
            
            total_products = len(products)
            low_stock_products = sum(1 for p in products if p.requires_stock_tracking and p.stock_quantity <= p.stock_alert)
            out_of_stock_products = sum(1 for p in products if p.requires_stock_tracking and p.stock_quantity <= 0)
            
            total_inventory_value = sum(
                p.stock_quantity * float(p.selling_price) 
                for p in products 
                if p.requires_stock_tracking
            )
            
            # Raw material statistics
            raw_materials = RawMaterial.query.filter_by(tenant_id=tenant_id).all()
            
            total_raw_materials = len(raw_materials)
            low_stock_raw_materials = sum(1 for rm in raw_materials if rm.stock_quantity <= rm.stock_alert)
            out_of_stock_raw_materials = sum(1 for rm in raw_materials if rm.stock_quantity <= 0)
            
            total_raw_material_value = sum(
                rm.stock_quantity * float(rm.cost_price)
                for rm in raw_materials
            )
            
            return {
                'products': {
                    'total': total_products,
                    'low_stock': low_stock_products,
                    'out_of_stock': out_of_stock_products,
                    'total_value': total_inventory_value
                },
                'raw_materials': {
                    'total': total_raw_materials,
                    'low_stock': low_stock_raw_materials,
                    'out_of_stock': out_of_stock_raw_materials,
                    'total_value': total_raw_material_value
                },
                'total_inventory_value': total_inventory_value + total_raw_material_value
            }
            
        except Exception as e:
            current_app.logger.error(f"Error calculating inventory stats: {str(e)}")
            return {}
    
    @staticmethod
    def _get_customer_stats(tenant_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get customer statistics"""
        try:
            # Total customers
            total_customers = Customer.query.filter_by(tenant_id=tenant_id).count()
            
            # Active customers (yang bertransaksi dalam period)
            active_customers = db.session.query(func.count(func.distinct(Sale.customer_id))).filter(
                Sale.tenant_id == tenant_id,
                Sale.customer_id.isnot(None),
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).scalar() or 0
            
            # New customers (registrasi dalam period)
            new_customers = Customer.query.filter(
                Customer.tenant_id == tenant_id,
                Customer.created_at >= start_date,
                Customer.created_at <= end_date
            ).count()
            
            return {
                'total_customers': total_customers,
                'active_customers': active_customers,
                'new_customers': new_customers,
                'activity_rate': round((active_customers / total_customers * 100) if total_customers > 0 else 0, 2)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error calculating customer stats: {str(e)}")
            return {}
    
    @staticmethod
    def _get_alert_stats(tenant_id: str) -> Dict:
        """Get alert statistics"""
        try:
            # Low stock alerts
            low_stock_products = Product.query.filter(
                Product.tenant_id == tenant_id,
                Product.requires_stock_tracking == True,
                Product.stock_quantity <= Product.stock_alert
            ).count()
            
            low_stock_raw_materials = RawMaterial.query.filter(
                RawMaterial.tenant_id == tenant_id,
                RawMaterial.stock_quantity <= RawMaterial.stock_alert
            ).count()
            
            # Critical alerts (out of stock)
            critical_products = Product.query.filter(
                Product.tenant_id == tenant_id,
                Product.requires_stock_tracking == True,
                Product.stock_quantity <= 0
            ).count()
            
            critical_raw_materials = RawMaterial.query.filter(
                RawMaterial.tenant_id == tenant_id,
                RawMaterial.stock_quantity <= 0
            ).count()
            
            total_alerts = low_stock_products + low_stock_raw_materials
            critical_alerts = critical_products + critical_raw_materials
            
            return {
                'total_alerts': total_alerts,
                'critical_alerts': critical_alerts,
                'low_stock_products': low_stock_products,
                'low_stock_raw_materials': low_stock_raw_materials,
                'alert_level': 'critical' if critical_alerts > 0 else 'warning' if total_alerts > 0 else 'normal'
            }
            
        except Exception as e:
            current_app.logger.error(f"Error calculating alert stats: {str(e)}")
            return {}
    
    @staticmethod
    def _get_performance_stats(tenant_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get performance statistics"""
        try:
            # Top selling products
            top_products = db.session.query(
                Product.name,
                func.sum(Sale.items.any().quantity).label('total_sold'),
                func.sum(Sale.items.any().subtotal).label('total_revenue')
            ).join(Sale.items).filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).group_by(Product.id, Product.name).order_by(
                func.sum(Sale.items.any().quantity).desc()
            ).limit(5).all()
            
            # Peak hours analysis
            hourly_sales = db.session.query(
                func.extract('hour', Sale.sale_date).label('hour'),
                func.count(Sale.id).label('transaction_count'),
                func.sum(Sale.total_amount).label('total_amount')
            ).filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).group_by(func.extract('hour', Sale.sale_date)).all()
            
            return {
                'top_products': [
                    {
                        'name': product[0],
                        'quantity_sold': int(product[1] or 0),
                        'revenue': float(product[2] or 0)
                    }
                    for product in top_products
                ],
                'hourly_performance': [
                    {
                        'hour': int(hour[0]),
                        'transaction_count': int(hour[1]),
                        'total_amount': float(hour[2])
                    }
                    for hour in hourly_sales
                ]
            }
            
        except Exception as e:
            current_app.logger.error(f"Error calculating performance stats: {str(e)}")
            return {}
    
    @staticmethod
    def get_sales_chart_data(tenant_id: str, chart_type: str, period: str = 'week') -> Dict:
        """Get sales chart data dengan caching"""
        try:
            # Check cache first
            cached_data = DashboardCacheService.get_cached_sales_chart_data(tenant_id, chart_type, period)
            if cached_data:
                return cached_data
            
            end_date = datetime.utcnow()
            
            if period == 'week':
                start_date = end_date - timedelta(days=7)
                date_format = '%Y-%m-%d'
            elif period == 'month':
                start_date = end_date - timedelta(days=30)
                date_format = '%Y-%m-%d'
            elif period == 'year':
                start_date = end_date - timedelta(days=365)
                date_format = '%Y-%m'
            else:
                start_date = end_date - timedelta(days=7)
                date_format = '%Y-%m-%d'
            
            chart_data = {}
            
            if chart_type == 'daily_sales':
                chart_data = EnhancedDashboardService._get_daily_sales_chart(
                    tenant_id, start_date, end_date, date_format
                )
            elif chart_type == 'product_performance':
                chart_data = EnhancedDashboardService._get_product_performance_chart(
                    tenant_id, start_date, end_date
                )
            elif chart_type == 'hourly_sales':
                chart_data = EnhancedDashboardService._get_hourly_sales_chart(
                    tenant_id, start_date, end_date
                )
            elif chart_type == 'category_breakdown':
                chart_data = EnhancedDashboardService._get_category_breakdown_chart(
                    tenant_id, start_date, end_date
                )
            
            # Cache the chart data
            DashboardCacheService.cache_sales_chart_data(tenant_id, chart_type, period, chart_data)
            
            return chart_data
            
        except Exception as e:
            current_app.logger.error(f"Error getting sales chart data: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _get_daily_sales_chart(tenant_id: str, start_date: datetime, end_date: datetime, date_format: str) -> Dict:
        """Get daily sales chart data"""
        try:
            daily_sales = db.session.query(
                func.date(Sale.sale_date).label('sale_date'),
                func.count(Sale.id).label('transaction_count'),
                func.sum(Sale.total_amount).label('total_amount')
            ).filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).group_by(func.date(Sale.sale_date)).order_by(func.date(Sale.sale_date)).all()
            
            return {
                'type': 'line',
                'title': 'Daily Sales Performance',
                'labels': [day[0].strftime(date_format) for day in daily_sales],
                'datasets': [
                    {
                        'label': 'Revenue',
                        'data': [float(day[2]) for day in daily_sales],
                        'borderColor': 'rgb(75, 192, 192)',
                        'backgroundColor': 'rgba(75, 192, 192, 0.2)'
                    },
                    {
                        'label': 'Transactions',
                        'data': [int(day[1]) for day in daily_sales],
                        'borderColor': 'rgb(255, 99, 132)',
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                        'yAxisID': 'y1'
                    }
                ]
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting daily sales chart: {str(e)}")
            return {}
    
    @staticmethod
    def _get_product_performance_chart(tenant_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get product performance chart data"""
        try:
            # This is a simplified version - you might need to adjust based on your actual Sale-Product relationship
            top_products = db.session.query(
                Product.name,
                func.sum(Sale.total_amount).label('revenue')
            ).join(Sale).filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).group_by(Product.id, Product.name).order_by(
                func.sum(Sale.total_amount).desc()
            ).limit(10).all()
            
            return {
                'type': 'bar',
                'title': 'Top Products by Revenue',
                'labels': [product[0] for product in top_products],
                'datasets': [{
                    'label': 'Revenue',
                    'data': [float(product[1]) for product in top_products],
                    'backgroundColor': [
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 205, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)',
                        'rgba(255, 159, 64, 0.8)',
                        'rgba(199, 199, 199, 0.8)',
                        'rgba(83, 102, 255, 0.8)',
                        'rgba(255, 99, 255, 0.8)',
                        'rgba(99, 255, 132, 0.8)'
                    ]
                }]
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting product performance chart: {str(e)}")
            return {}
    
    @staticmethod
    def _get_hourly_sales_chart(tenant_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get hourly sales pattern chart"""
        try:
            hourly_data = db.session.query(
                func.extract('hour', Sale.sale_date).label('hour'),
                func.count(Sale.id).label('transaction_count'),
                func.sum(Sale.total_amount).label('total_amount')
            ).filter(
                Sale.tenant_id == tenant_id,
                Sale.sale_date >= start_date,
                Sale.sale_date <= end_date
            ).group_by(func.extract('hour', Sale.sale_date)).order_by(
                func.extract('hour', Sale.sale_date)
            ).all()
            
            # Fill missing hours dengan 0
            hours_data = {int(hour[0]): {'count': int(hour[1]), 'amount': float(hour[2])} for hour in hourly_data}
            
            labels = [f"{hour:02d}:00" for hour in range(24)]
            transaction_data = [hours_data.get(hour, {'count': 0, 'amount': 0})['count'] for hour in range(24)]
            amount_data = [hours_data.get(hour, {'count': 0, 'amount': 0})['amount'] for hour in range(24)]
            
            return {
                'type': 'line',
                'title': 'Hourly Sales Pattern',
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Transactions',
                        'data': transaction_data,
                        'borderColor': 'rgb(54, 162, 235)',
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)'
                    },
                    {
                        'label': 'Revenue',
                        'data': amount_data,
                        'borderColor': 'rgb(255, 99, 132)',
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                        'yAxisID': 'y1'
                    }
                ]
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting hourly sales chart: {str(e)}")
            return {}
    
    @staticmethod
    def _get_category_breakdown_chart(tenant_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get category breakdown chart (placeholder - adjust based on your category model)"""
        try:
            # This is a placeholder implementation
            # You'll need to adjust based on your actual category/product relationship
            
            return {
                'type': 'doughnut',
                'title': 'Sales by Category',
                'labels': ['Category A', 'Category B', 'Category C'],
                'datasets': [{
                    'data': [30, 40, 30],
                    'backgroundColor': [
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 205, 86, 0.8)'
                    ]
                }]
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting category breakdown chart: {str(e)}")
            return {}
    
    @staticmethod
    def invalidate_dashboard_cache(tenant_id: str):
        """Invalidate semua dashboard cache untuk tenant"""
        DashboardCacheService.invalidate_dashboard_cache(tenant_id)

    @staticmethod
    def _get_recent_activity_data(tenant_id: str) -> List[Dict]:
        """Get recent activity data untuk dashboard"""
        try:
            recent_sales = Sale.query.filter_by(
                tenant_id=tenant_id
            ).order_by(Sale.created_at.desc()).limit(10).all()
            
            activity_data = []
            for sale in recent_sales:
                # Convert UTC time to user's local time
                from app.utils.timezone import convert_utc_to_user_timezone
                local_time = convert_utc_to_user_timezone(sale.created_at)
                
                activity_data.append({
                    'type': 'sale',
                    'title': f'New Sale - {sale.receipt_number}',
                    'description': f'Rp{sale.total_amount:.2f} • {sale.payment_method}',
                    'time': local_time.strftime('%H:%M'),
                    'date': local_time.strftime('%Y-%m-%d'),
                    'datetime': local_time.isoformat(),
                    'icon': 'bi-cart-check'
                })
            
            return activity_data
            
        except Exception as e:
            current_app.logger.error(f"Error getting recent activity data: {str(e)}")
            return []
    
    @staticmethod
    def _get_top_products_data(tenant_id: str, days: int, limit: int) -> List[Dict]:
        """Get top products data untuk dashboard"""
        try:
            from app.utils.timezone import local_to_utc
            from datetime import datetime, timedelta
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_utc = local_to_utc(start_date.replace(hour=0, minute=0, second=0, microsecond=0))
            
            top_products = db.session.query(
                Product.name,
                func.sum(SaleItem.quantity).label('total_sold'),
                func.sum(SaleItem.total_price).label('revenue')
            ).join(SaleItem, Product.id == SaleItem.product_id)\
             .join(Sale, SaleItem.sale_id == Sale.id)\
             .filter(
                 Sale.tenant_id == tenant_id,
                 Sale.created_at >= start_date_utc
             ).group_by(Product.id, Product.name)\
             .order_by(func.sum(SaleItem.quantity).desc())\
             .limit(limit).all()
            
            products_data = []
            for product in top_products:
                products_data.append({
                    'name': product.name,
                    'sold': int(product.total_sold) if product.total_sold else 0,
                    'revenue': float(product.revenue) if product.revenue else 0.0
                })
            
            return products_data
            
        except Exception as e:
            current_app.logger.error(f"Error getting top products data: {str(e)}")
            return []

    @staticmethod
    def get_recent_activity(tenant_id: str) -> List[Dict]:
        """Public method untuk mendapatkan recent activity"""
        return EnhancedDashboardService._get_recent_activity_data(tenant_id)
    
    @staticmethod
    def get_top_products(tenant_id: str, days: int = 30, limit: int = 10) -> List[Dict]:
        """Public method untuk mendapatkan top products"""
        return EnhancedDashboardService._get_top_products_data(tenant_id, days, limit)