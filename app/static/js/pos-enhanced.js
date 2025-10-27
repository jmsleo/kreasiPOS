class EnhancedPOSSystem {
    constructor() {
        this.cart = [];
        this.subtotal = 0;
        this.taxRate = 0.1; // 10% tax
        this.taxAmount = 0;
        this.discountAmount = 0;
        this.totalAmount = 0;
        this.currentCustomer = null;
        this.barcodeInput = '';
        this.barcodeTimeout = null;
        this.bomValidationCache = new Map();
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateCartDisplay();
        this.loadProducts();
        this.setupBarcodeScanner();
        this.initBOMValidation();
    }

    bindEvents() {
        // Product click events
        document.querySelectorAll('.product-card').forEach(card => {
            card.addEventListener('click', () => {
                const productId = card.dataset.productId;
                this.addToCart(productId);
            });
        });

        // Barcode scanner simulation
        document.addEventListener('keydown', (e) => {
            this.handleBarcodeInput(e);
        });

        // Payment method
        document.getElementById('paymentMethod')?.addEventListener('change', (e) => {
            this.updateTotals();
        });

        // Customer selection
        document.getElementById('customerSelect')?.addEventListener('change', (e) => {
            this.currentCustomer = e.target.value;
        });

        // Process sale
        document.getElementById('processSale')?.addEventListener('click', () => {
            this.processSale();
        });

        // Clear cart
        document.getElementById('clearCart')?.addEventListener('click', () => {
            this.clearCart();
        });

        // Product search
        document.getElementById('productSearch')?.addEventListener('input', (e) => {
            this.filterProducts(e.target.value);
        });

        // Discount application
        document.getElementById('applyDiscount')?.addEventListener('click', () => {
            this.applyDiscount();
        });

        // Quick quantity buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-qty')) {
                const productId = e.target.dataset.productId;
                const quantity = parseInt(e.target.dataset.quantity);
                this.setQuantity(productId, quantity);
            }
        });

        // BOM validation toggle
        document.getElementById('bomValidationToggle')?.addEventListener('change', (e) => {
            this.bomValidationEnabled = e.target.checked;
            this.validateAllBOMItems();
        });
    }

    initBOMValidation() {
        this.bomValidationEnabled = true;
        this.createBOMValidationPanel();
    }

    createBOMValidationPanel() {
        const cartContainer = document.getElementById('cartContainer');
        if (!cartContainer) return;

        const bomPanel = document.createElement('div');
        bomPanel.id = 'bomValidationPanel';
        bomPanel.className = 'card mt-3';
        bomPanel.innerHTML = `
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">BOM Validation</h6>
                <div class="form-check form-switch">
                    <input class="form-check-input" type="checkbox" id="bomValidationToggle" checked>
                    <label class="form-check-label" for="bomValidationToggle">Enable</label>
                </div>
            </div>
            <div class="card-body">
                <div id="bomValidationResults"></div>
            </div>
        `;
        
        cartContainer.appendChild(bomPanel);
        
        // Re-bind the toggle event
        document.getElementById('bomValidationToggle').addEventListener('change', (e) => {
            this.bomValidationEnabled = e.target.checked;
            this.validateAllBOMItems();
        });
    }

    setupBarcodeScanner() {
        this.barcodeInput = '';
        this.barcodeTimeout = null;
    }

    handleBarcodeInput(e) {
        // Skip if typing in input fields
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        // Barcode scanners typically send characters quickly
        if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
            this.barcodeInput += e.key;
            
            // Clear previous timeout
            if (this.barcodeTimeout) {
                clearTimeout(this.barcodeTimeout);
            }
            
            // Set timeout to detect end of barcode input
            this.barcodeTimeout = setTimeout(() => {
                this.processBarcode(this.barcodeInput);
                this.barcodeInput = '';
            }, 100);
        }
        
        // Enter key also processes barcode
        if (e.key === 'Enter' && this.barcodeInput) {
            this.processBarcode(this.barcodeInput);
            this.barcodeInput = '';
            e.preventDefault();
        }
    }

    async processBarcode(barcode) {
        try {
            const response = await fetch(`/products/api/search?q=${encodeURIComponent(barcode)}`);
            const products = await response.json();
            
            if (products.length > 0) {
                const product = products[0];
                await this.addToCart(product.id);
                this.showNotification(`Added ${product.name} to cart`, 'success');
            } else {
                this.showNotification('Product not found', 'error');
            }
        } catch (error) {
            console.error('Barcode search error:', error);
            this.showNotification('Error searching product', 'error');
        }
    }

    async loadProducts() {
        try {
            const response = await fetch('/sales/api/products');
            const products = await response.json();
            this.renderProductsGrid(products);
        } catch (error) {
            console.error('Error loading products:', error);
        }
    }

    renderProductsGrid(products) {
        const grid = document.getElementById('productsGrid');
        if (!grid) return;
        
        grid.innerHTML = '';

        products.forEach(product => {
            const productCard = document.createElement('div');
            productCard.className = `product-card ${product.stock_quantity === 0 ? 'out-of-stock' : ''}`;
            productCard.dataset.productId = product.id;
            
            // BOM indicator
            const bomIndicator = product.has_bom ? 
                '<span class="badge bg-info position-absolute top-0 end-0 m-1">BOM</span>' : '';
            
            // Stock tracking indicator
            const stockIndicator = product.requires_stock_tracking ? 
                `<small class="text-muted">Stock: ${product.stock_quantity}</small>` :
                '<small class="text-info">No Stock Tracking</small>';
            
            productCard.innerHTML = `
                <div class="card h-100 position-relative">
                    ${bomIndicator}
                    <div class="card-body text-center">
                        ${product.image_url ? 
                            `<img src="${product.image_url}" alt="${product.name}" class="product-image mb-2">` : 
                            '<div class="product-placeholder mb-2"><i class="bi bi-image"></i></div>'
                        }
                        <h6 class="card-title">${product.name}</h6>
                        <p class="card-text text-success">$${product.price.toFixed(2)}</p>
                        ${stockIndicator}
                        ${product.stock_quantity === 0 && product.requires_stock_tracking ? 
                            '<span class="badge bg-danger">Out of Stock</span>' : ''
                        }
                        ${product.has_bom && !product.bom_available ? 
                            '<span class="badge bg-warning">BOM Materials Low</span>' : ''
                        }
                    </div>
                </div>
            `;
            grid.appendChild(productCard);
        });

        // Re-bind events untuk product cards baru
        document.querySelectorAll('.product-card').forEach(card => {
            card.addEventListener('click', () => {
                const productId = card.dataset.productId;
                this.addToCart(productId);
            });
        });
    }

    async getProductData(productId) {
        try {
            const response = await fetch(`/products/api/${productId}`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching product data:', error);
            return null;
        }
    }

    async validateBOMAvailability(productId, quantity = 1) {
        if (!this.bomValidationEnabled) return { valid: true, message: 'BOM validation disabled' };
        
        try {
            console.log(`Validating BOM for product ${productId}, quantity ${quantity}`);
            
            const response = await fetch('/bom/api/validate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    product_id: productId,
                    quantity: quantity
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            console.log('BOM validation result:', result);
            
            return {
                valid: result.valid || false,
                message: result.message || 'Unknown validation result',
                details: result.details || [],
                missing_items: result.missing_items || []
            };
        } catch (error) {
            console.error('BOM validation error:', error);
            return { 
                valid: false, 
                message: 'BOM validation failed due to network error',
                error: error.message 
            };
        }
    }

    async addToCart(productId) {
        const product = await this.getProductData(productId);
        if (!product) {
            this.showNotification('Product not found', 'error');
            return;
        }

        // Check stock for products that require stock tracking
        if (product.requires_stock_tracking && product.stock_quantity <= 0) {
            this.showNotification('Product out of stock', 'error');
            return;
        }

        const existingItem = this.cart.find(item => item.product_id === productId);
        const newQuantity = existingItem ? existingItem.quantity + 1 : 1;

        // Validate BOM if product has BOM
        if (product.has_bom) {
            console.log(`Product ${product.name} has BOM, validating availability...`);
            const bomValidation = await this.validateBOMAvailability(productId, newQuantity);
            
            if (!bomValidation.valid) {
                let errorMessage = `BOM validation failed for ${product.name}: ${bomValidation.message}`;
                
                if (bomValidation.missing_items && bomValidation.missing_items.length > 0) {
                    const missingNames = bomValidation.missing_items.map(item => 
                        `${item.name} (shortage: ${item.shortage} ${item.unit})`
                    ).join(', ');
                    errorMessage += `\n\nMissing materials: ${missingNames}`;
                }
                
                this.showNotification(errorMessage, 'error');
                
                // Don't allow adding to cart if BOM validation fails
                if (this.bomValidationEnabled) {
                    return;
                }
            } else {
                console.log(`BOM validation passed for ${product.name}`);
            }
        }

        // Check stock limit for products with stock tracking
        if (product.requires_stock_tracking && existingItem && existingItem.quantity >= product.stock_quantity) {
            this.showNotification('Not enough stock available', 'error');
            return;
        }

        if (existingItem) {
            existingItem.quantity += 1;
            existingItem.total_price = existingItem.quantity * existingItem.unit_price;
        } else {
            this.cart.push({
                product_id: productId,
                name: product.name,
                quantity: 1,
                unit_price: product.price,
                total_price: product.price,
                has_bom: product.has_bom,
                requires_stock_tracking: product.requires_stock_tracking
            });
        }

        this.updateTotals();
        this.updateCartDisplay();
        this.validateAllBOMItems();
        this.showNotification(`Added ${product.name} to cart`, 'success');
    }

    async validateAllBOMItems() {
        if (!this.bomValidationEnabled) {
            const resultsEl = document.getElementById('bomValidationResults');
            if (resultsEl) {
                resultsEl.innerHTML = '<div class="text-muted">BOM validation is disabled</div>';
            }
            return;
        }

        const bomItems = this.cart.filter(item => item.has_bom);
        const resultsEl = document.getElementById('bomValidationResults');
        
        if (!resultsEl) return;
        
        if (bomItems.length === 0) {
            resultsEl.innerHTML = '<div class="text-muted">No BOM products in cart</div>';
            return;
        }

        let validationHtml = '';
        for (const item of bomItems) {
            console.log(`Validating BOM for cart item: ${item.name} (${item.quantity}x)`);
            const validation = await this.validateBOMAvailability(item.product_id, item.quantity);
            const statusClass = validation.valid ? 'text-success' : 'text-danger';
            const icon = validation.valid ? 'bi-check-circle' : 'bi-exclamation-triangle';
            
            let detailsHtml = '';
            if (!validation.valid && validation.missing_items && validation.missing_items.length > 0) {
                detailsHtml = '<br><small class="text-muted">Missing: ' + 
                    validation.missing_items.map(mi => `${mi.name} (${mi.shortage} ${mi.unit})`).join(', ') + 
                    '</small>';
            }
            
            validationHtml += `
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <span>${item.name} (${item.quantity}x)</span>
                        ${detailsHtml}
                    </div>
                    <span class="${statusClass}">
                        <i class="bi ${icon}"></i> ${validation.message}
                    </span>
                </div>
            `;
        }

        resultsEl.innerHTML = validationHtml;
    }

    removeFromCart(productId) {
        this.cart = this.cart.filter(item => item.product_id !== productId);
        this.updateTotals();
        this.updateCartDisplay();
        this.validateAllBOMItems();
    }

    async updateQuantity(productId, change) {
        const item = this.cart.find(item => item.product_id === productId);
        if (item) {
            const newQuantity = item.quantity + change;
            if (newQuantity <= 0) {
                this.removeFromCart(productId);
            } else {
                const product = await this.getProductData(productId);
                if (product && product.requires_stock_tracking && newQuantity > product.stock_quantity) {
                    this.showNotification('Not enough stock available', 'error');
                    return;
                }
                
                // Validate BOM for new quantity
                if (item.has_bom) {
                    const bomValidation = await this.validateBOMAvailability(productId, newQuantity);
                    if (!bomValidation.valid && this.bomValidationEnabled) {
                        this.showNotification(`BOM validation failed: ${bomValidation.message}`, 'error');
                        return;
                    }
                }
                
                item.quantity = newQuantity;
                item.total_price = item.quantity * item.unit_price;
                this.updateTotals();
                this.updateCartDisplay();
                this.validateAllBOMItems();
            }
        }
    }

    async setQuantity(productId, quantity) {
        const item = this.cart.find(item => item.product_id === productId);
        if (item) {
            const product = await this.getProductData(productId);
            if (product && product.requires_stock_tracking && quantity > product.stock_quantity) {
                this.showNotification('Not enough stock available', 'error');
                return;
            }
            
            // Validate BOM for new quantity
            if (item.has_bom) {
                const bomValidation = await this.validateBOMAvailability(productId, quantity);
                if (!bomValidation.valid && this.bomValidationEnabled) {
                    this.showNotification(`BOM validation failed: ${bomValidation.message}`, 'error');
                    return;
                }
            }
            
            item.quantity = quantity;
            item.total_price = item.quantity * item.unit_price;
            this.updateTotals();
            this.updateCartDisplay();
            this.validateAllBOMItems();
        }
    }

    updateTotals() {
        this.subtotal = this.cart.reduce((sum, item) => sum + item.total_price, 0);
        this.taxAmount = this.subtotal * this.taxRate;
        this.totalAmount = this.subtotal + this.taxAmount - this.discountAmount;

        this.updateDisplay();
    }

    updateDisplay() {
        const subtotalEl = document.getElementById('subtotal');
        const taxEl = document.getElementById('tax');
        const discountEl = document.getElementById('discount');
        const totalEl = document.getElementById('total');
        
        if (subtotalEl) subtotalEl.textContent = this.subtotal.toFixed(2);
        if (taxEl) taxEl.textContent = this.taxAmount.toFixed(2);
        if (discountEl) discountEl.textContent = this.discountAmount.toFixed(2);
        if (totalEl) totalEl.textContent = this.totalAmount.toFixed(2);

        // Update process sale button state
        const processBtn = document.getElementById('processSale');
        if (processBtn) processBtn.disabled = this.cart.length === 0;
    }

    updateCartDisplay() {
        const cartItems = document.getElementById('cartItems');
        if (!cartItems) return;
        
        if (this.cart.length === 0) {
            cartItems.innerHTML = '<div class="text-center text-muted py-4">No items in cart</div>';
            return;
        }

        cartItems.innerHTML = this.cart.map(item => {
            const bomBadge = item.has_bom ? '<span class="badge bg-info ms-1">BOM</span>' : '';
            const stockBadge = !item.requires_stock_tracking ? '<span class="badge bg-secondary ms-1">No Stock</span>' : '';
            
            return `
                <div class="cart-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${item.name} ${bomBadge} ${stockBadge}</h6>
                            <div class="d-flex align-items-center">
                                <button class="btn btn-sm btn-outline-secondary me-2" 
                                        onclick="pos.updateQuantity('${item.product_id}', -1)">-</button>
                                <span class="mx-2">${item.quantity}</span>
                                <button class="btn btn-sm btn-outline-secondary ms-2" 
                                        onclick="pos.updateQuantity('${item.product_id}', 1)">+</button>
                                <div class="btn-group ms-3" role="group">
                                    <button type="button" class="btn btn-sm btn-outline-primary quick-qty" 
                                            data-product-id="${item.product_id}" data-quantity="5">5</button>
                                    <button type="button" class="btn btn-sm btn-outline-primary quick-qty" 
                                            data-product-id="${item.product_id}" data-quantity="10">10</button>
                                </div>
                                <small class="text-muted ms-3">$${item.unit_price.toFixed(2)} each</small>
                            </div>
                        </div>
                        <div class="text-end">
                            <div class="fw-bold">$${item.total_price.toFixed(2)}</div>
                            <button class="btn btn-sm btn-danger mt-1" 
                                    onclick="pos.removeFromCart('${item.product_id}')">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    applyDiscount() {
        const discountInput = document.getElementById('discountInput');
        if (!discountInput) return;
        
        const discountValue = parseFloat(discountInput.value);
        
        if (!isNaN(discountValue) && discountValue > 0) {
            if (discountValue <= this.subtotal) {
                this.discountAmount = discountValue;
                this.updateTotals();
                discountInput.value = '';
                this.showNotification('Discount applied', 'success');
            } else {
                this.showNotification('Discount cannot exceed subtotal', 'error');
            }
        } else {
            this.showNotification('Please enter a valid discount amount', 'error');
        }
    }

    async processSale() {
        if (this.cart.length === 0) {
            this.showNotification('Please add items to cart before processing sale.', 'error');
            return;
        }

        // Final BOM validation before processing
        const bomItems = this.cart.filter(item => item.has_bom);
        for (const item of bomItems) {
            console.log(`Final BOM validation for ${item.name} (${item.quantity}x)`);
            const validation = await this.validateBOMAvailability(item.product_id, item.quantity);
            if (!validation.valid && this.bomValidationEnabled) {
                let errorDetails = validation.message;
                if (validation.missing_items && validation.missing_items.length > 0) {
                    const missingList = validation.missing_items.map(mi => 
                        `${mi.name} (shortage: ${mi.shortage} ${mi.unit})`
                    ).join('\n- ');
                    errorDetails += `\n\nMissing materials:\n- ${missingList}`;
                }
                
                const proceed = confirm(`BOM validation failed for ${item.name}:\n${errorDetails}\n\nDo you want to proceed anyway?`);
                if (!proceed) return;
            }
        }

        const paymentMethod = document.getElementById('paymentMethod')?.value || 'cash';
        const customerId = document.getElementById('customerSelect')?.value;
        const notes = document.getElementById('saleNotes')?.value;

        const saleData = {
            items: this.cart,
            subtotal: this.subtotal,
            tax_amount: this.taxAmount,
            discount_amount: this.discountAmount,
            total_amount: this.totalAmount,
            payment_method: paymentMethod,
            customer_id: customerId || null,
            notes: notes,
            bom_validation_enabled: this.bomValidationEnabled
        };

        try {
            console.log('Processing sale with data:', saleData);
            
            const response = await fetch('/sales/process-sale', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(saleData)
            });

            const result = await response.json();
            console.log('Sale processing result:', result);

            if (result.success) {
                this.showNotification(`Sale processed successfully! Receipt: ${result.receipt_number}`, 'success');
                
                if (result.print_status) {
                    this.showNotification(result.print_message, 'info');
                } else {
                    setTimeout(() => {
                        if (confirm('Sale processed! Would you like to print the receipt?')) {
                            this.printReceipt(result.sale_id);
                        }
                    }, 1000);
                }
                
                this.clearCart();
                
                // Reset form
                if (document.getElementById('customerSelect')) document.getElementById('customerSelect').value = '';
                if (document.getElementById('saleNotes')) document.getElementById('saleNotes').value = '';
                
            } else {
                this.showNotification('Error processing sale: ' + result.error, 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showNotification('Error processing sale. Please try again.', 'error');
        }
    }

    clearCart() {
        this.cart = [];
        this.subtotal = 0;
        this.taxAmount = 0;
        this.discountAmount = 0;
        this.totalAmount = 0;
        this.updateTotals();
        this.updateCartDisplay();
        this.validateAllBOMItems();
    }

    filterProducts(searchTerm) {
        const products = document.querySelectorAll('.product-card');
        const term = searchTerm.toLowerCase();

        products.forEach(product => {
            const productName = product.querySelector('.card-title')?.textContent.toLowerCase();
            if (productName && productName.includes(term)) {
                product.style.display = 'block';
            } else {
                product.style.display = 'none';
            }
        });
    }

    async printReceipt(saleId) {
        try {
            const response = await fetch(`/sales/receipt/${saleId}/print`);
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Receipt sent to printer', 'success');
            } else {
                this.showNotification('Print failed: ' + result.message, 'error');
            }
        } catch (error) {
            console.error('Print error:', error);
            this.showNotification('Error printing receipt', 'error');
        }
    }

    getCSRFToken() {
        const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        return token || '';
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Add to notification container
        const container = document.getElementById('notificationContainer') || this.createNotificationContainer();
        container.appendChild(notification);
        
        // Auto remove after 5 seconds
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

// Initialize Enhanced POS system when page loads
document.addEventListener('DOMContentLoaded', function() {
    window.pos = new EnhancedPOSSystem();
});