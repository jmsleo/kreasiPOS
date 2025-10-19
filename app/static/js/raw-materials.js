class RawMaterialsManager {
    constructor() {
        this.currentPage = 1;
        this.itemsPerPage = 20;
        this.sortBy = 'name';
        this.sortOrder = 'asc';
        this.filterLowStock = false;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadRawMaterials();
        this.setupStockAlerts();
    }

    bindEvents() {
        // Search functionality
        document.getElementById('rawMaterialSearch')?.addEventListener('input', (e) => {
            this.searchRawMaterials(e.target.value);
        });

        // Filter buttons
        document.getElementById('filterLowStock')?.addEventListener('change', (e) => {
            this.filterLowStock = e.target.checked;
            this.loadRawMaterials();
        });

        // Sort dropdown
        document.getElementById('sortBy')?.addEventListener('change', (e) => {
            this.sortBy = e.target.value;
            this.loadRawMaterials();
        });

        // Sort order toggle
        document.getElementById('sortOrder')?.addEventListener('click', (e) => {
            this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
            e.target.innerHTML = this.sortOrder === 'asc' ? 
                '<i class="bi bi-sort-alpha-down"></i>' : 
                '<i class="bi bi-sort-alpha-up"></i>';
            this.loadRawMaterials();
        });

        // Bulk actions
        document.getElementById('selectAll')?.addEventListener('change', (e) => {
            this.selectAllItems(e.target.checked);
        });

        document.getElementById('bulkDelete')?.addEventListener('click', () => {
            this.bulkDeleteItems();
        });

        // Stock update buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('stock-update-btn')) {
                const materialId = e.target.dataset.materialId;
                this.showStockUpdateModal(materialId);
            }
        });

        // Quick stock adjustment
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-stock-btn')) {
                const materialId = e.target.dataset.materialId;
                const adjustment = parseInt(e.target.dataset.adjustment);
                this.quickStockAdjustment(materialId, adjustment);
            }
        });

        // Stock update form submission
        document.getElementById('stockUpdateForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.processStockUpdate();
        });
    }

    async loadRawMaterials() {
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: this.itemsPerPage,
                sort_by: this.sortBy,
                sort_order: this.sortOrder,
                low_stock_only: this.filterLowStock
            });

            const response = await fetch(`/raw-materials/api/list?${params}`);
            const data = await response.json();
            
            this.renderRawMaterials(data.raw_materials);
            this.renderPagination(data.pagination);
            this.updateStockSummary(data.summary);
        } catch (error) {
            console.error('Error loading raw materials:', error);
            this.showNotification('Error loading raw materials', 'error');
        }
    }

    renderRawMaterials(materials) {
        const tbody = document.getElementById('rawMaterialsTableBody');
        if (!tbody) return;

        if (materials.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center py-4">
                        <i class="bi bi-inbox display-4 text-muted"></i>
                        <h5 class="mt-3 text-muted">No raw materials found</h5>
                        <p class="text-muted">Try adjusting your filters or add new raw materials</p>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = materials.map(material => {
            const stockStatus = this.getStockStatus(material);
            const lowStockClass = material.is_low_stock ? 'table-warning' : '';
            
            return `
                <tr class="${lowStockClass}">
                    <td>
                        <input type="checkbox" class="form-check-input item-checkbox" 
                               value="${material.id}">
                    </td>
                    <td>
                        <div class="d-flex align-items-center">
                            <div>
                                <h6 class="mb-0">${material.name}</h6>
                                <small class="text-muted">${material.sku || 'No SKU'}</small>
                            </div>
                        </div>
                    </td>
                    <td>${material.unit}</td>
                    <td>
                        <div class="d-flex align-items-center">
                            <span class="me-2">${material.stock_quantity}</span>
                            ${stockStatus.badge}
                        </div>
                    </td>
                    <td>$${(material.cost_price || 0).toFixed(2)}</td>
                    <td>${material.stock_alert}</td>
                    <td>
                        <span class="badge ${material.is_active ? 'bg-success' : 'bg-secondary'}">
                            ${material.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </td>
                    <td>
                        <div class="btn-group btn-group-sm" role="group">
                            <button type="button" class="btn btn-outline-primary stock-update-btn" 
                                    data-material-id="${material.id}" title="Update Stock">
                                <i class="bi bi-plus-minus"></i>
                            </button>
                            <button type="button" class="btn btn-outline-secondary" 
                                    onclick="window.location.href='/raw-materials/${material.id}/edit'" title="Edit">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <div class="btn-group" role="group">
                                <button type="button" class="btn btn-outline-success btn-sm dropdown-toggle" 
                                        data-bs-toggle="dropdown" title="Quick Stock">
                                    <i class="bi bi-lightning"></i>
                                </button>
                                <ul class="dropdown-menu">
                                    <li><a class="dropdown-item quick-stock-btn" href="#" 
                                           data-material-id="${material.id}" data-adjustment="10">+10</a></li>
                                    <li><a class="dropdown-item quick-stock-btn" href="#" 
                                           data-material-id="${material.id}" data-adjustment="50">+50</a></li>
                                    <li><a class="dropdown-item quick-stock-btn" href="#" 
                                           data-material-id="${material.id}" data-adjustment="100">+100</a></li>
                                    <li><hr class="dropdown-divider"></li>
                                    <li><a class="dropdown-item quick-stock-btn" href="#" 
                                           data-material-id="${material.id}" data-adjustment="-10">-10</a></li>
                                    <li><a class="dropdown-item quick-stock-btn" href="#" 
                                           data-material-id="${material.id}" data-adjustment="-50">-50</a></li>
                                </ul>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    getStockStatus(material) {
        if (material.stock_quantity === 0) {
            return {
                badge: '<span class="badge bg-danger">Out of Stock</span>',
                class: 'danger'
            };
        } else if (material.is_low_stock) {
            return {
                badge: '<span class="badge bg-warning">Low Stock</span>',
                class: 'warning'
            };
        } else {
            return {
                badge: '<span class="badge bg-success">In Stock</span>',
                class: 'success'
            };
        }
    }

    renderPagination(pagination) {
        const container = document.getElementById('paginationContainer');
        if (!container || !pagination) return;

        const { current_page, total_pages, has_prev, has_next } = pagination;

        let paginationHtml = '<nav><ul class="pagination justify-content-center">';

        // Previous button
        paginationHtml += `
            <li class="page-item ${!has_prev ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="rawMaterialsManager.goToPage(${current_page - 1})" ${!has_prev ? 'tabindex="-1"' : ''}>
                    <i class="bi bi-chevron-left"></i>
                </a>
            </li>
        `;

        // Page numbers
        const startPage = Math.max(1, current_page - 2);
        const endPage = Math.min(total_pages, current_page + 2);

        for (let i = startPage; i <= endPage; i++) {
            paginationHtml += `
                <li class="page-item ${i === current_page ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="rawMaterialsManager.goToPage(${i})">${i}</a>
                </li>
            `;
        }

        // Next button
        paginationHtml += `
            <li class="page-item ${!has_next ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="rawMaterialsManager.goToPage(${current_page + 1})" ${!has_next ? 'tabindex="-1"' : ''}>
                    <i class="bi bi-chevron-right"></i>
                </a>
            </li>
        `;

        paginationHtml += '</ul></nav>';
        container.innerHTML = paginationHtml;
    }

    updateStockSummary(summary) {
        if (!summary) return;

        const summaryContainer = document.getElementById('stockSummary');
        if (summaryContainer) {
            summaryContainer.innerHTML = `
                <div class="row g-3">
                    <div class="col-md-3">
                        <div class="card bg-primary text-white">
                            <div class="card-body">
                                <h5 class="card-title">${summary.total_materials}</h5>
                                <p class="card-text">Total Materials</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-success text-white">
                            <div class="card-body">
                                <h5 class="card-title">${summary.in_stock}</h5>
                                <p class="card-text">In Stock</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-warning text-white">
                            <div class="card-body">
                                <h5 class="card-title">${summary.low_stock}</h5>
                                <p class="card-text">Low Stock</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card bg-danger text-white">
                            <div class="card-body">
                                <h5 class="card-title">${summary.out_of_stock}</h5>
                                <p class="card-text">Out of Stock</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    goToPage(page) {
        this.currentPage = page;
        this.loadRawMaterials();
    }

    searchRawMaterials(searchTerm) {
        const rows = document.querySelectorAll('#rawMaterialsTableBody tr');
        const term = searchTerm.toLowerCase();

        rows.forEach(row => {
            const name = row.querySelector('h6')?.textContent.toLowerCase();
            const sku = row.querySelector('small')?.textContent.toLowerCase();
            
            if (name?.includes(term) || sku?.includes(term)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    selectAllItems(checked) {
        document.querySelectorAll('.item-checkbox').forEach(checkbox => {
            checkbox.checked = checked;
        });
    }

    async bulkDeleteItems() {
        const selectedIds = Array.from(document.querySelectorAll('.item-checkbox:checked'))
            .map(cb => cb.value);

        if (selectedIds.length === 0) {
            this.showNotification('Please select items to delete', 'warning');
            return;
        }

        if (!confirm(`Are you sure you want to delete ${selectedIds.length} raw material(s)?`)) {
            return;
        }

        try {
            const response = await fetch('/raw-materials/api/bulk-delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ ids: selectedIds })
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification(`Successfully deleted ${result.deleted_count} raw material(s)`, 'success');
                this.loadRawMaterials();
            } else {
                this.showNotification('Error deleting raw materials: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error deleting raw materials:', error);
            this.showNotification('Error deleting raw materials', 'error');
        }
    }

    async showStockUpdateModal(materialId) {
        try {
            const response = await fetch(`/raw-materials/api/${materialId}`);
            const material = await response.json();
            
            // Populate stock update form
            document.getElementById('stockUpdateMaterialId').value = materialId;
            document.getElementById('stockUpdateMaterialName').textContent = material.name;
            document.getElementById('currentStock').textContent = material.stock_quantity;
            document.getElementById('stockAdjustment').value = '';
            document.getElementById('adjustmentReason').value = '';
            
            const modal = new bootstrap.Modal(document.getElementById('stockUpdateModal'));
            modal.show();
            
        } catch (error) {
            console.error('Error loading material for stock update:', error);
            this.showNotification('Error loading material', 'error');
        }
    }

    async processStockUpdate() {
        const formData = new FormData(document.getElementById('stockUpdateForm'));
        const updateData = {
            material_id: formData.get('material_id'),
            adjustment: parseInt(formData.get('stock_adjustment')),
            reason: formData.get('adjustment_reason'),
            adjustment_type: formData.get('adjustment_type') || 'manual'
        };

        if (!updateData.adjustment || updateData.adjustment === 0) {
            this.showNotification('Please enter a valid stock adjustment', 'error');
            return;
        }

        try {
            const response = await fetch('/raw-materials/api/stock-update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(updateData)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Stock updated successfully', 'success');
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('stockUpdateModal'));
                modal.hide();
                
                // Reload materials
                this.loadRawMaterials();
                
            } else {
                this.showNotification('Error updating stock: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error updating stock:', error);
            this.showNotification('Error updating stock', 'error');
        }
    }

    async quickStockAdjustment(materialId, adjustment) {
        try {
            const response = await fetch('/raw-materials/api/stock-update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    material_id: materialId,
                    adjustment: adjustment,
                    reason: `Quick adjustment: ${adjustment > 0 ? '+' : ''}${adjustment}`,
                    adjustment_type: 'quick'
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification(`Stock adjusted by ${adjustment > 0 ? '+' : ''}${adjustment}`, 'success');
                this.loadRawMaterials();
            } else {
                this.showNotification('Error adjusting stock: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error adjusting stock:', error);
            this.showNotification('Error adjusting stock', 'error');
        }
    }

    setupStockAlerts() {
        // Check for low stock alerts every 5 minutes
        setInterval(() => {
            this.checkStockAlerts();
        }, 300000);
        
        // Initial check
        this.checkStockAlerts();
    }

    async checkStockAlerts() {
        try {
            const response = await fetch('/raw-materials/api/stock-alerts');
            const alerts = await response.json();
            
            if (alerts.length > 0) {
                this.showStockAlerts(alerts);
            }
        } catch (error) {
            console.error('Error checking stock alerts:', error);
        }
    }

    showStockAlerts(alerts) {
        const alertContainer = document.getElementById('stockAlertsContainer') || this.createStockAlertsContainer();
        
        alerts.forEach(alert => {
            const alertElement = document.createElement('div');
            alertElement.className = 'alert alert-warning alert-dismissible fade show';
            alertElement.innerHTML = `
                <i class="bi bi-exclamation-triangle"></i>
                <strong>Low Stock Alert:</strong> ${alert.name} is running low (${alert.stock_quantity} ${alert.unit} remaining)
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            
            alertContainer.appendChild(alertElement);
            
            // Auto remove after 10 seconds
            setTimeout(() => {
                if (alertElement.parentElement) {
                    alertElement.remove();
                }
            }, 10000);
        });
    }

    createStockAlertsContainer() {
        const container = document.createElement('div');
        container.id = 'stockAlertsContainer';
        container.className = 'position-fixed top-0 start-0 p-3';
        container.style.zIndex = '1056';
        container.style.maxWidth = '400px';
        document.body.appendChild(container);
        return container;
    }

    getCSRFToken() {
        const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        return token || '';
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.getElementById('notificationContainer') || this.createNotificationContainer();
        container.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    createNotificationContainer() {
        const container = document.createElement('div');
        container.id = 'notificationContainer';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
        return container;
    }
}

// Initialize Raw Materials Manager when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('rawMaterialsTableBody')) {
        window.rawMaterialsManager = new RawMaterialsManager();
    }
});