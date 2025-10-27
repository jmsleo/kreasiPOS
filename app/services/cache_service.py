"""
Redis Cache Service untuk optimasi performa aplikasi POS
Menyediakan caching layer untuk data yang sering diakses
"""
import json
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Optional, Dict, List
from flask import current_app
from app.extensions import cache
import redis


class CacheService:
    """Service untuk mengelola Redis cache dengan berbagai strategi caching"""
    
    # Cache timeout configurations (dalam detik)
    CACHE_TIMEOUTS = {
        'short': 300,      # 5 menit - untuk data yang sering berubah
        'medium': 1800,    # 30 menit - untuk data semi-static
        'long': 3600,      # 1 jam - untuk data yang jarang berubah
        'daily': 86400,    # 24 jam - untuk data harian
        'weekly': 604800   # 7 hari - untuk data yang sangat stabil
    }
    
    @staticmethod
    def get_cache_key(prefix: str, *args, tenant_id: str = None) -> str:
        """Generate cache key dengan format yang konsisten"""
        key_parts = [prefix]
        
        if tenant_id:
            key_parts.append(f"tenant:{tenant_id}")
            
        # Tambahkan semua arguments
        for arg in args:
            if isinstance(arg, dict):
                # Untuk dict, buat hash dari sorted items
                arg_str = json.dumps(arg, sort_keys=True)
                key_parts.append(hashlib.md5(arg_str.encode()).hexdigest()[:8])
            else:
                key_parts.append(str(arg))
        
        return ":".join(key_parts)
    
    @staticmethod
    def set_cache(key: str, value: Any, timeout: str = 'medium') -> bool:
        """Set cache dengan timeout yang ditentukan"""
        try:
            timeout_seconds = CacheService.CACHE_TIMEOUTS.get(timeout, 1800)
            return cache.set(key, value, timeout=timeout_seconds)
        except Exception as e:
            # --- PERBAIKAN: Ubah {str(e)} menjadi {e!r} untuk log yang lebih baik ---
            current_app.logger.error(f"Cache set error for key {key}: {e!r}")
            return False
    
    @staticmethod
    def get_cache(key: str) -> Any:
        """Get cache value"""
        try:
            return cache.get(key)
        except Exception as e:
            # --- PERBAIKAN: Ubah {str(e)} menjadi {e!r} untuk log yang lebih baik ---
            current_app.logger.error(f"Cache get error for key {key}: {e!r}")
            return None
    
    @staticmethod
    def delete_cache(key: str) -> bool:
        """Delete cache key"""
        try:
            return cache.delete(key)
        except Exception as e:
            # --- PERBAIKAN: Ubah {str(e)} menjadi {e!r} untuk log yang lebih baik ---
            current_app.logger.error(f"Cache delete error for key {key}: {e!r}")
            return False
    
    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """Delete multiple cache keys by pattern"""
        try:
            # Get Redis connection dari Flask-Caching
            redis_client = cache.cache._write_client
            keys = redis_client.keys(pattern)
            if keys:
                return redis_client.delete(*keys)
            return 0
        except Exception as e:
            # --- PERBAIKAN: Ubah {str(e)} menjadi {e!r} untuk log yang lebih baik ---
            current_app.logger.error(f"Cache pattern delete error for pattern {pattern}: {e!r}")
            return 0
    
    @staticmethod
    def invalidate_tenant_cache(tenant_id: str, cache_type: str = None):
        """Invalidate semua cache untuk tenant tertentu"""
        if cache_type:
            pattern = f"{cache_type}:tenant:{tenant_id}:*"
        else:
            pattern = f"*:tenant:{tenant_id}:*"
        
        return CacheService.delete_pattern(pattern)
    
    @staticmethod
    def get_or_set(key: str, callback, timeout: str = 'medium', *args, **kwargs) -> Any:
        """Get from cache atau set jika tidak ada"""
        value = CacheService.get_cache(key)
        if value is not None:
            return value
        
        # Generate value menggunakan callback
        value = callback(*args, **kwargs)
        if value is not None:
            CacheService.set_cache(key, value, timeout)
        
        return value


class ProductCacheService:
    """Cache service khusus untuk product-related data"""
    
    @staticmethod
    def get_product_cache_key(product_id: str, tenant_id: str, suffix: str = "") -> str:
        return CacheService.get_cache_key("product", product_id, suffix, tenant_id=tenant_id)
    
    @staticmethod
    def cache_product_details(product_id: str, tenant_id: str, product_data: dict):
        """Cache product details"""
        key = ProductCacheService.get_product_cache_key(product_id, tenant_id, "details")
        CacheService.set_cache(key, product_data, 'medium')
    
    @staticmethod
    def get_cached_product_details(product_id: str, tenant_id: str) -> Optional[dict]:
        """Get cached product details"""
        key = ProductCacheService.get_product_cache_key(product_id, tenant_id, "details")
        return CacheService.get_cache(key)
    
    @staticmethod
    def invalidate_product_cache(product_id: str, tenant_id: str):
        """Invalidate semua cache untuk product tertentu"""
        pattern = f"product:{product_id}:*:tenant:{tenant_id}:*"
        return CacheService.delete_pattern(pattern)
    
    @staticmethod
    def cache_product_list(tenant_id: str, filters: dict, products: list):
        """Cache product list dengan filter tertentu"""
        key = CacheService.get_cache_key("product_list", filters, tenant_id=tenant_id)
        CacheService.set_cache(key, products, 'short')
    
    @staticmethod
    def get_cached_product_list(tenant_id: str, filters: dict) -> Optional[list]:
        """Get cached product list"""
        key = CacheService.get_cache_key("product_list", filters, tenant_id=tenant_id)
        return CacheService.get_cache(key)


class DashboardCacheService:
    """Cache service untuk dashboard statistics"""
    
    @staticmethod
    def cache_dashboard_stats(tenant_id: str, period: str, stats: dict):
        """Cache dashboard statistics"""
        key = CacheService.get_cache_key("dashboard_stats", period, tenant_id=tenant_id)
        CacheService.set_cache(key, stats, 'medium')
    
    @staticmethod
    def get_cached_dashboard_stats(tenant_id: str, period: str) -> Optional[dict]:
        """Get cached dashboard statistics"""
        key = CacheService.get_cache_key("dashboard_stats", period, tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def cache_sales_chart_data(tenant_id: str, chart_type: str, period: str, data: dict):
        """Cache sales chart data"""
        key = CacheService.get_cache_key("sales_chart", chart_type, period, tenant_id=tenant_id)
        CacheService.set_cache(key, data, 'medium')
    
    @staticmethod
    def get_cached_sales_chart_data(tenant_id: str, chart_type: str, period: str) -> Optional[dict]:
        """Get cached sales chart data"""
        key = CacheService.get_cache_key("sales_chart", chart_type, period, tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def invalidate_dashboard_cache(tenant_id: str):
        """Invalidate semua dashboard cache untuk tenant"""
        CacheService.delete_pattern(f"dashboard_stats:*:tenant:{tenant_id}:*")
        CacheService.delete_pattern(f"sales_chart:*:tenant:{tenant_id}:*")


class BOMCacheService:
    """Cache service untuk BOM calculations"""
    
    @staticmethod
    def cache_bom_calculation(product_id: str, tenant_id: str, quantity: int, calculation: dict):
        """Cache BOM calculation result"""
        key = CacheService.get_cache_key("bom_calc", product_id, quantity, tenant_id=tenant_id)
        CacheService.set_cache(key, calculation, 'short')
    
    @staticmethod
    def get_cached_bom_calculation(product_id: str, tenant_id: str, quantity: int) -> Optional[dict]:
        """Get cached BOM calculation"""
        key = CacheService.get_cache_key("bom_calc", product_id, quantity, tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def cache_bom_availability(product_id: str, tenant_id: str, availability: dict):
        """Cache BOM availability check"""
        key = CacheService.get_cache_key("bom_avail", product_id, tenant_id=tenant_id)
        CacheService.set_cache(key, availability, 'short')
    
    @staticmethod
    def get_cached_bom_availability(product_id: str, tenant_id: str) -> Optional[dict]:
        """Get cached BOM availability"""
        key = CacheService.get_cache_key("bom_avail", product_id, tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def invalidate_bom_cache(product_id: str, tenant_id: str):
        """Invalidate BOM cache untuk product tertentu"""
        CacheService.delete_pattern(f"bom_calc:{product_id}:*:tenant:{tenant_id}:*")
        CacheService.delete_pattern(f"bom_avail:{product_id}:*:tenant:{tenant_id}:*")


class UserCacheService:
    """Cache service untuk user authentication dan profile data"""
    
    @staticmethod
    def cache_user_permissions(user_id: str, tenant_id: str, permissions: dict):
        """Cache user permissions"""
        key = CacheService.get_cache_key("user_perms", user_id, tenant_id=tenant_id)
        CacheService.set_cache(key, permissions, 'long')
    
    @staticmethod
    def get_cached_user_permissions(user_id: str, tenant_id: str) -> Optional[dict]:
        """Get cached user permissions"""
        key = CacheService.get_cache_key("user_perms", user_id, tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def invalidate_user_cache(user_id: str, tenant_id: str = None):
        """Invalidate user cache"""
        if tenant_id:
            pattern = f"user_perms:{user_id}:tenant:{tenant_id}:*"
        else:
            pattern = f"user_perms:{user_id}:*"
        CacheService.delete_pattern(pattern)


def cache_result(timeout: str = 'medium', key_prefix: str = None):
    """Decorator untuk caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_prefix:
                cache_key = CacheService.get_cache_key(key_prefix, *args, **kwargs)
            else:
                cache_key = CacheService.get_cache_key(func.__name__, *args, **kwargs)
            
            # Try to get from cache
            result = CacheService.get_cache(cache_key)
            if result is not None:
                return result
            
            # Execute function dan cache result
            result = func(*args, **kwargs)
            if result is not None:
                CacheService.set_cache(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


class InventoryCacheService:
    """Cache service untuk inventory-related data"""
    
    @staticmethod
    def cache_stock_levels(tenant_id: str, stock_data: dict):
        """Cache current stock levels"""
        key = CacheService.get_cache_key("stock_levels", tenant_id=tenant_id)
        CacheService.set_cache(key, stock_data, 'short')
    
    @staticmethod
    def get_cached_stock_levels(tenant_id: str) -> Optional[dict]:
        """Get cached stock levels"""
        key = CacheService.get_cache_key("stock_levels", tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def cache_low_stock_alerts(tenant_id: str, alerts: list):
        """Cache low stock alerts"""
        key = CacheService.get_cache_key("low_stock_alerts", tenant_id=tenant_id)
        CacheService.set_cache(key, alerts, 'medium')
    
    @staticmethod
    def get_cached_low_stock_alerts(tenant_id: str) -> Optional[list]:
        """Get cached low stock alerts"""
        key = CacheService.get_cache_key("low_stock_alerts", tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def invalidate_inventory_cache(tenant_id: str):
        """Invalidate inventory cache"""
        CacheService.delete_pattern(f"stock_levels:tenant:{tenant_id}:*")
        CacheService.delete_pattern(f"low_stock_alerts:tenant:{tenant_id}:*")


class ReportsCacheService:
    """Cache service untuk reports dan analytics"""
    
    @staticmethod
    def cache_sales_report(tenant_id: str, report_type: str, period: str, filters: dict, report_data: dict):
        """Cache sales report data"""
        key = CacheService.get_cache_key("sales_report", report_type, period, filters, tenant_id=tenant_id)
        CacheService.set_cache(key, report_data, 'medium')
    
    @staticmethod
    def get_cached_sales_report(tenant_id: str, report_type: str, period: str, filters: dict) -> Optional[dict]:
        """Get cached sales report"""
        key = CacheService.get_cache_key("sales_report", report_type, period, filters, tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def cache_inventory_report(tenant_id: str, report_type: str, report_data: dict):
        """Cache inventory report data"""
        key = CacheService.get_cache_key("inventory_report", report_type, tenant_id=tenant_id)
        CacheService.set_cache(key, report_data, 'medium')
    
    @staticmethod
    def get_cached_inventory_report(tenant_id: str, report_type: str) -> Optional[dict]:
        """Get cached inventory report"""
        key = CacheService.get_cache_key("inventory_report", report_type, tenant_id=tenant_id)
        return CacheService.get_cache(key)
    
    @staticmethod
    def invalidate_reports_cache(tenant_id: str):
        """Invalidate semua reports cache"""
        CacheService.delete_pattern(f"sales_report:*:tenant:{tenant_id}:*")
        CacheService.delete_pattern(f"inventory_report:*:tenant:{tenant_id}:*")