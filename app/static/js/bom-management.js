class BOMManagement {
    constructor() {
        this.bomItems = [];
        this.totalCost = 0;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadRawMaterials();
        this.loadExistingBOM();
    }

    bindEvents() {
        // Add BOM item button
        document.getElementById('addBOMItem')?.addEventListener('click', () => {
            this.addBOMItem();
        });

        // Save BOM button
        document.getElementById('saveBOM')?.addEventListener('click', () => {
            this.saveBOM();
        });

        // Cancel BOM button
        document.getElementById('cancelBOM')?.addEventListener('click', () => {
            this.cancelBOM();
        });

        // BOM enable/disable toggle
        document.getElementById('hasBOM')?.addEventListener('change', (e) => {
            this.toggleBOMSection(e.target.checked);
        });

        // Real-time cost calculation
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('bom-quantity')) {
                this.calculateTotalCost();
            }
        });

        // Raw material selection change
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('raw-material-select')) {
                this.updateMaterialInfo(e.target);
                this.calculateTotalCost();
            }
        });
    }

    async loadRawMaterials() {
        try {
            const response = await fetch('/raw-materials/api/list');
            const rawMaterials = await response.json();
            this.rawMaterials = rawMaterials;
            this.updateRawMaterialSelects();
        } catch (error) {
            console.error('Error loading raw materials:', error);
        }
    }

    async loadExistingBOM() {
        const productId = document.getElementById('productId')?.value;
        if (!productId) return;

        try {
            const response = await fetch(`/bom/api/product/${productId}`);
            if (response.ok) {
                const bomData = await response.json();
                if (bomData.bom_header) {
                    this.bomItems = bomData.bom_header.items || [];
                    this.renderBOMItems();
                    this.calculateTotalCost();
                }
            }
        } catch (error) {
            console.error('Error loading existing BOM:', error);
        }
    }

    toggleBOMSection(enabled) {
        const bomSection = document.getElementById('bomSection');
        if (bomSection) {
            bomSection.style.display = enabled ? 'block' : 'none';
        }

        if (enabled && this.bomItems.length === 0) {
            this.addBOMItem();
        }
    }

    addBOMItem() {
        const bomItem = {
            id: 'new_' + Date.now(),
            raw_material_id: '',
            raw_material_name: '',
            quantity: 1,
            unit: 'kg',
            cost_per_unit: 0,
            total_cost: 0
        };

        this.bomItems.push(bomItem);
        this.renderBOMItems();
    }

    removeBOMItem(itemId) {
        this.bomItems = this.bomItems.filter(item => item.id !== itemId);
        this.renderBOMItems();
        this.calculateTotalCost();
    }

    renderBOMItems() {
        const container = document.getElementById('bomItemsContainer');
        if (!container) return;

        container.innerHTML = '';

        this.bomItems.forEach((item, index) => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'bom-item card mb-3';
            itemDiv.innerHTML = `
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col-md-4">
                            <label class="form-label">Raw Material</label>
                            <select class="form-select raw-material-select" data-item-id="${item.id}">
                                <option value="">Select Raw Material</option>
                                ${this.rawMaterials ? this.rawMaterials.map(rm => 
                                    `<option value="${rm.id}" ${rm.id === item.raw_material_id ? 'selected' : ''}>
                                        ${rm.name} (${rm.unit}) - Stock: ${rm.stock_quantity}
                                    </option>`
                                ).join('') : ''}
                            </select>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Quantity</label>
                            <input type="number" class="form-control bom-quantity" 
                                   data-item-id="${item.id}" 
                                   value="${item.quantity}" 
                                   min="0" step="0.001">
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Unit</label>
                            <input type="text" class="form-control bom-unit" 
                                   data-item-id="${item.id}" 
                                   value="${item.unit}" readonly>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Cost/Unit</label>
                            <input type="number" class="form-control" 
                                   value="${item.cost_per_unit}" readonly>
                        </div>
                        <div class="col-md-1">
                            <label class="form-label">Total</label>
                            <div class="fw-bold">$${item.total_cost.toFixed(2)}</div>
                        </div>
                        <div class="col-md-1">
                            <label class="form-label">&nbsp;</label>
                            <button type="button" class="btn btn-danger btn-sm d-block" 
                                    onclick="bomManager.removeBOMItem('${item.id}')">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
            container.appendChild(itemDiv);
        });

        this.updateRawMaterialSelects();
    }

    updateRawMaterialSelects() {
        document.querySelectorAll('.raw-material-select').forEach(select => {
            if (!select.innerHTML.includes('Select Raw Material')) {
                select.innerHTML = `
                    <option value="">Select Raw Material</option>
                    ${this.rawMaterials ? this.rawMaterials.map(rm => 
                        `<option value="${rm.id}">
                            ${rm.name} (${rm.unit}) - Stock: ${rm.stock_quantity}
                        </option>`
                    ).join('') : ''}
                `;
            }
        });
    }

    updateMaterialInfo(selectElement) {
        const itemId = selectElement.dataset.itemId;
        const selectedMaterialId = selectElement.value;
        const item = this.bomItems.find(item => item.id === itemId);
        
        if (item && selectedMaterialId) {
            const material = this.rawMaterials.find(rm => rm.id === selectedMaterialId);
            if (material) {
                item.raw_material_id = material.id;
                item.raw_material_name = material.name;
                item.unit = material.unit;
                item.cost_per_unit = material.cost_price || 0;
                
                // Update unit field
                const unitInput = document.querySelector(`input.bom-unit[data-item-id="${itemId}"]`);
                if (unitInput) unitInput.value = material.unit;
                
                // Update cost per unit display
                const costInput = selectElement.closest('.row').querySelector('input[readonly]');
                if (costInput) costInput.value = material.cost_price || 0;
                
                this.calculateTotalCost();
            }
        }
    }

    calculateTotalCost() {
        this.totalCost = 0;

        this.bomItems.forEach(item => {
            const quantityInput = document.querySelector(`input.bom-quantity[data-item-id="${item.id}"]`);
            if (quantityInput) {
                item.quantity = parseFloat(quantityInput.value) || 0;
            }
            
            item.total_cost = item.quantity * (item.cost_per_unit || 0);
            this.totalCost += item.total_cost;

            // Update total cost display for this item
            const totalDiv = quantityInput?.closest('.row').querySelector('.fw-bold');
            if (totalDiv) {
                totalDiv.textContent = `$${item.total_cost.toFixed(2)}`;
            }
        });

        // Update total BOM cost display
        const totalCostElement = document.getElementById('bomTotalCost');
        if (totalCostElement) {
            totalCostElement.textContent = `$${this.totalCost.toFixed(2)}`;
        }

        // Update product BOM cost field
        const bomCostInput = document.getElementById('bomCost');
        if (bomCostInput) {
            bomCostInput.value = this.totalCost.toFixed(2);
        }
    }

    async validateBOM() {
        const errors = [];

        if (this.bomItems.length === 0) {
            errors.push('BOM must have at least one item');
        }

        this.bomItems.forEach((item, index) => {
            if (!item.raw_material_id) {
                errors.push(`Item ${index + 1}: Please select a raw material`);
            }
            if (!item.quantity || item.quantity <= 0) {
                errors.push(`Item ${index + 1}: Quantity must be greater than 0`);
            }
        });

        return {
            valid: errors.length === 0,
            errors: errors
        };
    }

    async saveBOM() {
        const validation = await this.validateBOM();
        if (!validation.valid) {
            alert('BOM validation failed:\n' + validation.errors.join('\n'));
            return;
        }

        const productId = document.getElementById('productId')?.value;
        if (!productId) {
            alert('Product ID not found');
            return;
        }

        // Update quantities from form inputs
        this.bomItems.forEach(item => {
            const quantityInput = document.querySelector(`input.bom-quantity[data-item-id="${item.id}"]`);
            if (quantityInput) {
                item.quantity = parseFloat(quantityInput.value) || 0;
            }
        });

        const bomData = {
            product_id: productId,
            items: this.bomItems.map(item => ({
                raw_material_id: item.raw_material_id,
                quantity: item.quantity,
                unit: item.unit,
                notes: item.notes || ''
            })),
            notes: document.getElementById('bomNotes')?.value || ''
        };

        try {
            const response = await fetch(`/bom/api/product/${productId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(bomData)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('BOM saved successfully', 'success');
                
                // Update product BOM cost
                const bomCostInput = document.getElementById('bomCost');
                if (bomCostInput) {
                    bomCostInput.value = result.bom_cost || this.totalCost;
                }
                
                // Reload BOM data
                await this.loadExistingBOM();
            } else {
                this.showNotification('Error saving BOM: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error saving BOM:', error);
            this.showNotification('Error saving BOM', 'error');
        }
    }

    cancelBOM() {
        if (confirm('Are you sure you want to cancel? Unsaved changes will be lost.')) {
            this.loadExistingBOM();
        }
    }

    async deleteBOM() {
        if (!confirm('Are you sure you want to delete this BOM? This action cannot be undone.')) {
            return;
        }

        const productId = document.getElementById('productId')?.value;
        if (!productId) return;

        try {
            const response = await fetch(`/bom/api/product/${productId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('BOM deleted successfully', 'success');
                this.bomItems = [];
                this.renderBOMItems();
                this.calculateTotalCost();
                
                // Uncheck BOM checkbox
                const hasBOMCheckbox = document.getElementById('hasBOM');
                if (hasBOMCheckbox) {
                    hasBOMCheckbox.checked = false;
                    this.toggleBOMSection(false);
                }
            } else {
                this.showNotification('Error deleting BOM: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error deleting BOM:', error);
            this.showNotification('Error deleting BOM', 'error');
        }
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

// Initialize BOM Management when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('bomSection') || document.getElementById('hasBOM')) {
        window.bomManager = new BOMManagement();
    }
});