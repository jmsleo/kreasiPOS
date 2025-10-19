class POSSystem {
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
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateCartDisplay();
        this.loadProducts();
        this.setupBarcodeScanner();
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
        document.getElementById('paymentMethod').addEventListener('change', (e) => {
            this.updateTotals();
        });

        // Customer selection
        document.getElementById('customerSelect').addEventListener('change', (e) => {
            this.currentCustomer = e.target.value;
        });

        // Process sale
        document.getElementById('processSale').addEventListener('click', () => {
            this.processSale();
        });

        // Clear cart
        document.getElementById('clearCart').addEventListener('click', () => {
            this.clearCart();
        });

        // Product search
        document.getElementById('productSearch').addEventListener('input', (e) => {
            this.filterProducts(e.target.value);
        });

        // Discount application
        document.getElementById('applyDiscount').addEventListener('click', () => {
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
    }

    setupBarcodeScanner() {
        // Barcode scanner akan menangani input keyboard
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
                this.addToCart(product.id);
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
        grid.innerHTML = '';

        products.forEach(product => {
            const productCard = document.createElement('div');
            productCard.className = `product-card ${product.stock_quantity === 0 ? 'out-of-stock' : ''}`;
            productCard.dataset.productId = product.id;
            productCard.innerHTML = `
                <div class="card h-100">
                    <div class="card-body text-center">
                        ${product.image_url ? 
                            `<img src="${product.image_url}" alt="${product.name}" class="product-image mb-2">` : 
                            '<div class="product-placeholder mb-2"><i class="bi bi-image"></i></div>'
                        }
                        <h6 class="card-title">${product.name}</h6>
                        <p class="card-text text-success">$${product.price.toFixed(2)}</p>
                        <small class="text-muted">Stock: ${product.stock_quantity}</small>
                        ${product.stock_quantity === 0 ? 
                            '<span class="badge bg-danger">Out of Stock</span>' : ''
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

    getProductData(productId) {
        const productElement = document.querySelector(`[data-product-id="${productId}"]`);
        if (productElement) {
            const name = productElement.querySelector('.card-title').textContent;
            const priceText = productElement.querySelector('.card-text').textContent;
            const price = parseFloat(priceText.replace('$', ''));
            const stockText = productElement.querySelector('.text-muted').textContent;
            const stock = parseInt(stockText.replace('Stock: ', ''));
            
            return { id: productId, name, price, stock_quantity: stock };
        }
        return null;
    }

    addToCart(productId) {
        const product = this.getProductData(productId);
        if (!product) {
            this.showNotification('Product not found', 'error');
            return;
        }

        if (product.stock_quantity <= 0) {
            this.showNotification('Product out of stock', 'error');
            return;
        }

        const existingItem = this.cart.find(item => item.product_id === productId);
        
        if (existingItem) {
            if (existingItem.quantity >= product.stock_quantity) {
                this.showNotification('Not enough stock available', 'error');
                return;
            }
            existingItem.quantity += 1;
            existingItem.total_price = existingItem.quantity * existingItem.unit_price;
        } else {
            this.cart.push({
                product_id: productId,
                name: product.name,
                quantity: 1,
                unit_price: product.price,
                total_price: product.price
            });
        }

        this.updateTotals();
        this.updateCartDisplay();
        this.showNotification(`Added ${product.name} to cart`, 'success');
    }

    removeFromCart(productId) {
        this.cart = this.cart.filter(item => item.product_id !== productId);
        this.updateTotals();
        this.updateCartDisplay();
    }

    updateQuantity(productId, change) {
        const item = this.cart.find(item => item.product_id === productId);
        if (item) {
            const newQuantity = item.quantity + change;
            if (newQuantity <= 0) {
                this.removeFromCart(productId);
            } else {
                const product = this.getProductData(productId);
                if (product && newQuantity > product.stock_quantity) {
                    this.showNotification('Not enough stock available', 'error');
                    return;
                }
                item.quantity = newQuantity;
                item.total_price = item.quantity * item.unit_price;
                this.updateTotals();
                this.updateCartDisplay();
            }
        }
    }

    setQuantity(productId, quantity) {
        const item = this.cart.find(item => item.product_id === productId);
        if (item) {
            const product = this.getProductData(productId);
            if (product && quantity > product.stock_quantity) {
                this.showNotification('Not enough stock available', 'error');
                return;
            }
            item.quantity = quantity;
            item.total_price = item.quantity * item.unit_price;
            this.updateTotals();
            this.updateCartDisplay();
        }
    }

    updateTotals() {
        this.subtotal = this.cart.reduce((sum, item) => sum + item.total_price, 0);
        this.taxAmount = this.subtotal * this.taxRate;
        this.totalAmount = this.subtotal + this.taxAmount - this.discountAmount;

        this.updateDisplay();
    }

    updateDisplay() {
        document.getElementById('subtotal').textContent = this.subtotal.toFixed(2);
        document.getElementById('tax').textContent = this.taxAmount.toFixed(2);
        document.getElementById('discount').textContent = this.discountAmount.toFixed(2);
        document.getElementById('total').textContent = this.totalAmount.toFixed(2);

        // Update process sale button state
        const processBtn = document.getElementById('processSale');
        processBtn.disabled = this.cart.length === 0;
    }

    updateCartDisplay() {
        const cartItems = document.getElementById('cartItems');
        
        if (this.cart.length === 0) {
            cartItems.innerHTML = '<div class="text-center text-muted py-4">No items in cart</div>';
            return;
        }

        cartItems.innerHTML = this.cart.map(item => `
            <div class="cart-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${item.name}</h6>
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
        `).join('');
    }

    applyDiscount() {
        const discountInput = document.getElementById('discountInput');
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

        const paymentMethod = document.getElementById('paymentMethod').value;
        const customerId = document.getElementById('customerSelect').value;
        const notes = document.getElementById('saleNotes').value;

        const saleData = {
            items: this.cart,
            subtotal: this.subtotal,
            tax_amount: this.taxAmount,
            discount_amount: this.discountAmount,
            total_amount: this.totalAmount,
            payment_method: paymentMethod,
            customer_id: customerId || null,
            notes: notes
        };

        try {
            const response = await fetch('/sales/process-sale', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(saleData)
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification(`Sale processed successfully! Receipt: ${result.receipt_number}`, 'success');
                
                // Tanya apakah ingin print receipt
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
                document.getElementById('customerSelect').value = '';
                document.getElementById('saleNotes').value = '';
                
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
    }

    filterProducts(searchTerm) {
        const products = document.querySelectorAll('.product-card');
        const term = searchTerm.toLowerCase();

        products.forEach(product => {
            const productName = product.querySelector('.card-title').textContent.toLowerCase();
            if (productName.includes(term)) {
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
        return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
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

// Initialize POS system when page loads
document.addEventListener('DOMContentLoaded', function() {
    window.pos = new POSSystem();
});