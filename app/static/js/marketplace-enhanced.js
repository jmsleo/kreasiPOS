class EnhancedMarketplace {
    constructor() {
        this.currentFilter = 'all';
        this.currentPage = 1;
        this.itemsPerPage = 12;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadMarketplaceItems();
    }

    bindEvents() {
        // Item type filter buttons
        document.querySelectorAll('.item-type-filter').forEach(button => {
            button.addEventListener('click', (e) => {
                this.setFilter(e.target.dataset.filter);
            });
        });

        // Search functionality
        document.getElementById('marketplaceSearch')?.addEventListener('input', (e) => {
            this.filterItems(e.target.value);
        });

        // Purchase buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('purchase-btn')) {
                const itemId = e.target.dataset.itemId;
                this.showPurchaseModal(itemId);
            }
        });

        // Purchase form submission
        document.getElementById('purchaseForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.processPurchase();
        });

        // Item type selection in create/edit form
        document.getElementById('itemType')?.addEventListener('change', (e) => {
            this.toggleItemTypeFields(e.target.value);
        });
    }

    setFilter(filter) {
        this.currentFilter = filter;
        this.currentPage = 1;
        
        // Update active filter button
        document.querySelectorAll('.item-type-filter').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-filter="${filter}"]`)?.classList.add('active');
        
        this.loadMarketplaceItems();
    }

    async loadMarketplaceItems() {
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: this.itemsPerPage
            });

            if (this.currentFilter !== 'all') {
                params.append('item_type', this.currentFilter);
            }

            const response = await fetch(`/marketplace/api/items?${params}`);
            const data = await response.json();
            
            this.renderMarketplaceItems(data.items);
            this.renderPagination(data.pagination);
        } catch (error) {
            console.error('Error loading marketplace items:', error);
            this.showNotification('Error loading marketplace items', 'error');
        }
    }

    renderMarketplaceItems(items) {
        const container = document.getElementById('marketplaceItemsGrid');
        if (!container) return;

        if (items.length === 0) {
            container.innerHTML = `
                <div class="col-12">
                    <div class="text-center py-5">
                        <i class="bi bi-inbox display-4 text-muted"></i>
                        <h5 class="mt-3 text-muted">No items found</h5>
                        <p class="text-muted">Try adjusting your filters or search terms</p>
                    </div>
                </div>
            `;
            return;
        }

        container.innerHTML = items.map(item => {
            const itemTypeBadge = this.getItemTypeBadge(item.item_type);
            const stockBadge = item.stock > 0 ? 
                `<span class="badge bg-success">Stock: ${item.stock}</span>` :
                `<span class="badge bg-danger">Out of Stock</span>`;

            return `
                <div class="col-md-4 col-lg-3 mb-4">
                    <div class="card h-100 marketplace-item">
                        <div class="position-relative">
                            ${item.image_url ? 
                                `<img src="${item.image_url}" class="card-img-top" alt="${item.name}" style="height: 200px; object-fit: cover;">` :
                                `<div class="card-img-top bg-light d-flex align-items-center justify-content-center" style="height: 200px;">
                                    <i class="bi bi-image display-4 text-muted"></i>
                                </div>`
                            }
                            <div class="position-absolute top-0 start-0 m-2">
                                ${itemTypeBadge}
                            </div>
                        </div>
                        <div class="card-body d-flex flex-column">
                            <h6 class="card-title">${item.name}</h6>
                            <p class="card-text text-muted small flex-grow-1">${item.description || 'No description available'}</p>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="fw-bold text-success">$${item.price.toFixed(2)}</span>
                                ${stockBadge}
                            </div>
                            <div class="d-flex gap-2">
                                <button class="btn btn-primary btn-sm purchase-btn flex-grow-1" 
                                        data-item-id="${item.id}" 
                                        ${item.stock === 0 ? 'disabled' : ''}>
                                    <i class="bi bi-cart-plus"></i> Purchase
                                </button>
                                <button class="btn btn-outline-secondary btn-sm" 
                                        onclick="marketplace.showItemDetails('${item.id}')">
                                    <i class="bi bi-eye"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    getItemTypeBadge(itemType) {
        switch (itemType) {
            case 'product':
                return '<span class="badge bg-primary">Product</span>';
            case 'raw_material':
                return '<span class="badge bg-warning">Raw Material</span>';
            default:
                return '<span class="badge bg-secondary">Unknown</span>';
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
                <a class="page-link" href="#" onclick="marketplace.goToPage(${current_page - 1})" ${!has_prev ? 'tabindex="-1"' : ''}>
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
                    <a class="page-link" href="#" onclick="marketplace.goToPage(${i})">${i}</a>
                </li>
            `;
        }

        // Next button
        paginationHtml += `
            <li class="page-item ${!has_next ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="marketplace.goToPage(${current_page + 1})" ${!has_next ? 'tabindex="-1"' : ''}>
                    <i class="bi bi-chevron-right"></i>
                </a>
            </li>
        `;

        paginationHtml += '</ul></nav>';
        container.innerHTML = paginationHtml;
    }

    goToPage(page) {
        this.currentPage = page;
        this.loadMarketplaceItems();
    }

    filterItems(searchTerm) {
        const items = document.querySelectorAll('.marketplace-item');
        const term = searchTerm.toLowerCase();

        items.forEach(item => {
            const title = item.querySelector('.card-title')?.textContent.toLowerCase();
            const description = item.querySelector('.card-text')?.textContent.toLowerCase();
            
            if (title?.includes(term) || description?.includes(term)) {
                item.closest('.col-md-4').style.display = 'block';
            } else {
                item.closest('.col-md-4').style.display = 'none';
            }
        });
    }

    async showItemDetails(itemId) {
        try {
            const response = await fetch(`/marketplace/api/items/${itemId}`);
            const item = await response.json();
            
            const modal = new bootstrap.Modal(document.getElementById('itemDetailsModal'));
            
            // Populate modal with item details
            document.getElementById('modalItemName').textContent = item.name;
            document.getElementById('modalItemDescription').textContent = item.description || 'No description available';
            document.getElementById('modalItemPrice').textContent = `$${item.price.toFixed(2)}`;
            document.getElementById('modalItemStock').textContent = item.stock;
            document.getElementById('modalItemType').innerHTML = this.getItemTypeBadge(item.item_type);
            
            const modalImage = document.getElementById('modalItemImage');
            if (item.image_url) {
                modalImage.src = item.image_url;
                modalImage.style.display = 'block';
            } else {
                modalImage.style.display = 'none';
            }
            
            // Set purchase button
            const purchaseBtn = document.getElementById('modalPurchaseBtn');
            purchaseBtn.dataset.itemId = itemId;
            purchaseBtn.disabled = item.stock === 0;
            
            modal.show();
        } catch (error) {
            console.error('Error loading item details:', error);
            this.showNotification('Error loading item details', 'error');
        }
    }

    async showPurchaseModal(itemId) {
        try {
            const response = await fetch(`/marketplace/api/items/${itemId}`);
            const item = await response.json();
            
            // Populate purchase form
            document.getElementById('purchaseItemId').value = itemId;
            document.getElementById('purchaseItemName').textContent = item.name;
            document.getElementById('purchaseItemPrice').textContent = `$${item.price.toFixed(2)}`;
            document.getElementById('purchaseItemType').innerHTML = this.getItemTypeBadge(item.item_type);
            document.getElementById('purchaseQuantity').max = item.stock;
            document.getElementById('purchaseQuantity').value = 1;
            
            // Calculate initial total
            this.updatePurchaseTotal();
            
            const modal = new bootstrap.Modal(document.getElementById('purchaseModal'));
            modal.show();
            
            // Bind quantity change event
            document.getElementById('purchaseQuantity').addEventListener('input', () => {
                this.updatePurchaseTotal();
            });
            
        } catch (error) {
            console.error('Error loading item for purchase:', error);
            this.showNotification('Error loading item', 'error');
        }
    }

    updatePurchaseTotal() {
        const quantity = parseInt(document.getElementById('purchaseQuantity').value) || 0;
        const priceText = document.getElementById('purchaseItemPrice').textContent;
        const price = parseFloat(priceText.replace('$', ''));
        const total = quantity * price;
        
        document.getElementById('purchaseTotal').textContent = `$${total.toFixed(2)}`;
    }

    async processPurchase() {
        const formData = new FormData(document.getElementById('purchaseForm'));
        const purchaseData = {
            marketplace_item_id: formData.get('item_id'),
            quantity: parseInt(formData.get('quantity')),
            shipping_address: formData.get('shipping_address'),
            shipping_city: formData.get('shipping_city'),
            shipping_postal_code: formData.get('shipping_postal_code'),
            shipping_phone: formData.get('shipping_phone'),
            notes: formData.get('notes')
        };

        try {
            const response = await fetch('/marketplace/purchase', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(purchaseData)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('Purchase order submitted successfully!', 'success');
                
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('purchaseModal'));
                modal.hide();
                
                // Reset form
                document.getElementById('purchaseForm').reset();
                
                // Reload items to update stock
                this.loadMarketplaceItems();
                
                // Show order details
                setTimeout(() => {
                    this.showNotification(`Order ID: ${result.order_id}. Please upload payment proof to complete your order.`, 'info');
                }, 1000);
                
            } else {
                this.showNotification('Error processing purchase: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error processing purchase:', error);
            this.showNotification('Error processing purchase', 'error');
        }
    }

    toggleItemTypeFields(itemType) {
        const productFields = document.getElementById('productFields');
        const rawMaterialFields = document.getElementById('rawMaterialFields');
        
        if (productFields && rawMaterialFields) {
            if (itemType === 'product') {
                productFields.style.display = 'block';
                rawMaterialFields.style.display = 'none';
            } else if (itemType === 'raw_material') {
                productFields.style.display = 'none';
                rawMaterialFields.style.display = 'block';
            } else {
                productFields.style.display = 'none';
                rawMaterialFields.style.display = 'none';
            }
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

// Initialize Enhanced Marketplace when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('marketplaceItemsGrid')) {
        window.marketplace = new EnhancedMarketplace();
    }
});