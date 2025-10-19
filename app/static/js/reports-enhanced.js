class EnhancedReports {
    constructor() {
        this.charts = {};
        this.currentDateRange = 'week';
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadReportData();
        this.setupChartInteractivity();
    }

    bindEvents() {
        // Date range selector
        document.getElementById('dateRange')?.addEventListener('change', (e) => {
            this.currentDateRange = e.target.value;
            this.loadReportData();
        });

        // Custom date range
        document.getElementById('customDateFrom')?.addEventListener('change', () => {
            if (this.currentDateRange === 'custom') {
                this.loadReportData();
            }
        });

        document.getElementById('customDateTo')?.addEventListener('change', () => {
            if (this.currentDateRange === 'custom') {
                this.loadReportData();
            }
        });

        // Report type tabs
        document.querySelectorAll('.report-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchReportTab(e.target.dataset.reportType);
            });
        });

        // Export buttons
        document.getElementById('exportPDF')?.addEventListener('click', () => {
            this.exportReport('pdf');
        });

        document.getElementById('exportExcel')?.addEventListener('click', () => {
            this.exportReport('excel');
        });

        // Refresh button
        document.getElementById('refreshReports')?.addEventListener('click', () => {
            this.loadReportData();
        });
    }

    async loadReportData() {
        try {
            const params = this.getDateRangeParams();
            const response = await fetch(`/reports/api/data?${params}`);
            const data = await response.json();
            
            this.renderSalesChart(data.sales_data);
            this.renderInventoryChart(data.inventory_data);
            this.renderBOMAnalysisChart(data.bom_data);
            this.renderTopProductsChart(data.top_products);
            this.updateKPIs(data.kpis);
            this.updateInventoryAlerts(data.inventory_alerts);
            
        } catch (error) {
            console.error('Error loading report data:', error);
            this.showNotification('Error loading report data', 'error');
        }
    }

    getDateRangeParams() {
        const params = new URLSearchParams();
        params.append('range', this.currentDateRange);
        
        if (this.currentDateRange === 'custom') {
            const fromDate = document.getElementById('customDateFrom')?.value;
            const toDate = document.getElementById('customDateTo')?.value;
            if (fromDate) params.append('from_date', fromDate);
            if (toDate) params.append('to_date', toDate);
        }
        
        return params.toString();
    }

    renderSalesChart(salesData) {
        const ctx = document.getElementById('salesChart')?.getContext('2d');
        if (!ctx || !salesData) return;

        // Destroy existing chart
        if (this.charts.sales) {
            this.charts.sales.destroy();
        }

        this.charts.sales = new Chart(ctx, {
            type: 'line',
            data: {
                labels: salesData.labels,
                datasets: [{
                    label: 'Sales Amount',
                    data: salesData.amounts,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.1,
                    fill: true
                }, {
                    label: 'Transaction Count',
                    data: salesData.counts,
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Sales Amount ($)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Transaction Count'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                return salesData.labels[context[0].dataIndex];
                            },
                            afterBody: function(context) {
                                const index = context[0].dataIndex;
                                return [
                                    `Transactions: ${salesData.counts[index]}`,
                                    `Average: $${(salesData.amounts[index] / salesData.counts[index]).toFixed(2)}`
                                ];
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const date = salesData.labels[index];
                        this.drillDownSalesData(date);
                    }
                }
            }
        });
    }

    renderInventoryChart(inventoryData) {
        const ctx = document.getElementById('inventoryChart')?.getContext('2d');
        if (!ctx || !inventoryData) return;

        if (this.charts.inventory) {
            this.charts.inventory.destroy();
        }

        this.charts.inventory = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['In Stock', 'Low Stock', 'Out of Stock'],
                datasets: [{
                    data: [
                        inventoryData.in_stock,
                        inventoryData.low_stock,
                        inventoryData.out_of_stock
                    ],
                    backgroundColor: [
                        'rgb(34, 197, 94)',
                        'rgb(251, 191, 36)',
                        'rgb(239, 68, 68)'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label;
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const status = ['in_stock', 'low_stock', 'out_of_stock'][index];
                        this.drillDownInventoryData(status);
                    }
                }
            }
        });
    }

    renderBOMAnalysisChart(bomData) {
        const ctx = document.getElementById('bomAnalysisChart')?.getContext('2d');
        if (!ctx || !bomData) return;

        if (this.charts.bomAnalysis) {
            this.charts.bomAnalysis.destroy();
        }

        this.charts.bomAnalysis = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: bomData.products,
                datasets: [{
                    label: 'BOM Cost',
                    data: bomData.bom_costs,
                    backgroundColor: 'rgba(99, 102, 241, 0.8)',
                    borderColor: 'rgb(99, 102, 241)',
                    borderWidth: 1
                }, {
                    label: 'Selling Price',
                    data: bomData.selling_prices,
                    backgroundColor: 'rgba(34, 197, 94, 0.8)',
                    borderColor: 'rgb(34, 197, 94)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Amount ($)'
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            afterBody: function(context) {
                                const index = context[0].dataIndex;
                                const bomCost = bomData.bom_costs[index];
                                const sellingPrice = bomData.selling_prices[index];
                                const margin = sellingPrice - bomCost;
                                const marginPercent = ((margin / sellingPrice) * 100).toFixed(1);
                                return [
                                    `Profit Margin: $${margin.toFixed(2)}`,
                                    `Margin %: ${marginPercent}%`
                                ];
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const productName = bomData.products[index];
                        this.drillDownBOMData(productName);
                    }
                }
            }
        });
    }

    renderTopProductsChart(topProductsData) {
        const ctx = document.getElementById('topProductsChart')?.getContext('2d');
        if (!ctx || !topProductsData) return;

        if (this.charts.topProducts) {
            this.charts.topProducts.destroy();
        }

        this.charts.topProducts = new Chart(ctx, {
            type: 'horizontalBar',
            data: {
                labels: topProductsData.products,
                datasets: [{
                    label: 'Quantity Sold',
                    data: topProductsData.quantities,
                    backgroundColor: 'rgba(168, 85, 247, 0.8)',
                    borderColor: 'rgb(168, 85, 247)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Quantity Sold'
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            afterBody: function(context) {
                                const index = context[0].dataIndex;
                                return [
                                    `Revenue: $${topProductsData.revenues[index].toFixed(2)}`,
                                    `Avg Price: $${topProductsData.avg_prices[index].toFixed(2)}`
                                ];
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const productName = topProductsData.products[index];
                        this.drillDownProductData(productName);
                    }
                }
            }
        });
    }

    updateKPIs(kpis) {
        if (!kpis) return;

        // Update KPI cards
        const kpiElements = {
            'totalSales': kpis.total_sales,
            'totalTransactions': kpis.total_transactions,
            'averageTransaction': kpis.average_transaction,
            'topProduct': kpis.top_product,
            'lowStockItems': kpis.low_stock_items,
            'bomProducts': kpis.bom_products,
            'rawMaterialsUsed': kpis.raw_materials_used,
            'profitMargin': kpis.profit_margin
        };

        Object.entries(kpiElements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                if (typeof value === 'number') {
                    if (id.includes('Sales') || id.includes('Transaction') || id.includes('Margin')) {
                        element.textContent = `$${value.toFixed(2)}`;
                    } else {
                        element.textContent = value.toLocaleString();
                    }
                } else {
                    element.textContent = value || 'N/A';
                }
            }
        });
    }

    updateInventoryAlerts(alerts) {
        const alertsContainer = document.getElementById('inventoryAlerts');
        if (!alertsContainer || !alerts) return;

        if (alerts.length === 0) {
            alertsContainer.innerHTML = `
                <div class="alert alert-success">
                    <i class="bi bi-check-circle"></i>
                    All inventory levels are healthy
                </div>
            `;
            return;
        }

        alertsContainer.innerHTML = alerts.map(alert => `
            <div class="alert alert-${alert.type} alert-dismissible">
                <i class="bi bi-${alert.type === 'danger' ? 'exclamation-triangle' : 'info-circle'}"></i>
                <strong>${alert.title}:</strong> ${alert.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `).join('');
    }

    setupChartInteractivity() {
        // Add click handlers for chart drill-down functionality
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('chart-drill-down')) {
                const chartType = e.target.dataset.chartType;
                const value = e.target.dataset.value;
                this.handleChartDrillDown(chartType, value);
            }
        });
    }

    async drillDownSalesData(date) {
        try {
            const response = await fetch(`/reports/api/sales-detail?date=${date}`);
            const data = await response.json();
            
            this.showDrillDownModal('Sales Detail', data, 'sales');
        } catch (error) {
            console.error('Error loading sales detail:', error);
            this.showNotification('Error loading sales detail', 'error');
        }
    }

    async drillDownInventoryData(status) {
        try {
            const response = await fetch(`/reports/api/inventory-detail?status=${status}`);
            const data = await response.json();
            
            this.showDrillDownModal('Inventory Detail', data, 'inventory');
        } catch (error) {
            console.error('Error loading inventory detail:', error);
            this.showNotification('Error loading inventory detail', 'error');
        }
    }

    async drillDownBOMData(productName) {
        try {
            const response = await fetch(`/reports/api/bom-detail?product=${encodeURIComponent(productName)}`);
            const data = await response.json();
            
            this.showDrillDownModal('BOM Analysis', data, 'bom');
        } catch (error) {
            console.error('Error loading BOM detail:', error);
            this.showNotification('Error loading BOM detail', 'error');
        }
    }

    async drillDownProductData(productName) {
        try {
            const response = await fetch(`/reports/api/product-detail?product=${encodeURIComponent(productName)}`);
            const data = await response.json();
            
            this.showDrillDownModal('Product Analysis', data, 'product');
        } catch (error) {
            console.error('Error loading product detail:', error);
            this.showNotification('Error loading product detail', 'error');
        }
    }

    showDrillDownModal(title, data, type) {
        const modal = document.getElementById('drillDownModal') || this.createDrillDownModal();
        
        // Update modal title
        modal.querySelector('.modal-title').textContent = title;
        
        // Update modal body based on type
        const modalBody = modal.querySelector('.modal-body');
        modalBody.innerHTML = this.generateDrillDownContent(data, type);
        
        // Show modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    generateDrillDownContent(data, type) {
        switch (type) {
            case 'sales':
                return this.generateSalesDrillDown(data);
            case 'inventory':
                return this.generateInventoryDrillDown(data);
            case 'bom':
                return this.generateBOMDrillDown(data);
            case 'product':
                return this.generateProductDrillDown(data);
            default:
                return '<p>No data available</p>';
        }
    }

    generateSalesDrillDown(data) {
        if (!data.transactions || data.transactions.length === 0) {
            return '<p>No transactions found for this period</p>';
        }

        return `
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Receipt #</th>
                            <th>Time</th>
                            <th>Items</th>
                            <th>Amount</th>
                            <th>Payment</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.transactions.map(tx => `
                            <tr>
                                <td>${tx.receipt_number}</td>
                                <td>${new Date(tx.created_at).toLocaleTimeString()}</td>
                                <td>${tx.item_count}</td>
                                <td>$${tx.total_amount.toFixed(2)}</td>
                                <td>${tx.payment_method}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    generateInventoryDrillDown(data) {
        if (!data.items || data.items.length === 0) {
            return '<p>No items found</p>';
        }

        return `
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Item</th>
                            <th>Type</th>
                            <th>Current Stock</th>
                            <th>Alert Level</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.items.map(item => `
                            <tr>
                                <td>${item.name}</td>
                                <td>${item.type}</td>
                                <td>${item.stock_quantity}</td>
                                <td>${item.stock_alert}</td>
                                <td>
                                    <span class="badge bg-${item.status_class}">
                                        ${item.status}
                                    </span>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    generateBOMDrillDown(data) {
        if (!data.bom_items || data.bom_items.length === 0) {
            return '<p>No BOM data found for this product</p>';
        }

        return `
            <div class="mb-3">
                <h6>Product: ${data.product_name}</h6>
                <p><strong>Total BOM Cost:</strong> $${data.total_bom_cost.toFixed(2)}</p>
                <p><strong>Selling Price:</strong> $${data.selling_price.toFixed(2)}</p>
                <p><strong>Profit Margin:</strong> $${(data.selling_price - data.total_bom_cost).toFixed(2)} (${(((data.selling_price - data.total_bom_cost) / data.selling_price) * 100).toFixed(1)}%)</p>
            </div>
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Raw Material</th>
                            <th>Quantity</th>
                            <th>Unit</th>
                            <th>Cost/Unit</th>
                            <th>Total Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.bom_items.map(item => `
                            <tr>
                                <td>${item.raw_material_name}</td>
                                <td>${item.quantity}</td>
                                <td>${item.unit}</td>
                                <td>$${item.cost_per_unit.toFixed(2)}</td>
                                <td>$${item.total_cost.toFixed(2)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    generateProductDrillDown(data) {
        return `
            <div class="row">
                <div class="col-md-6">
                    <h6>Sales Performance</h6>
                    <ul class="list-unstyled">
                        <li><strong>Total Sold:</strong> ${data.total_quantity}</li>
                        <li><strong>Total Revenue:</strong> $${data.total_revenue.toFixed(2)}</li>
                        <li><strong>Average Price:</strong> $${data.average_price.toFixed(2)}</li>
                        <li><strong>Last Sale:</strong> ${data.last_sale_date || 'Never'}</li>
                    </ul>
                </div>
                <div class="col-md-6">
                    <h6>Inventory Status</h6>
                    <ul class="list-unstyled">
                        <li><strong>Current Stock:</strong> ${data.current_stock}</li>
                        <li><strong>Stock Tracking:</strong> ${data.requires_stock_tracking ? 'Enabled' : 'Disabled'}</li>
                        <li><strong>Has BOM:</strong> ${data.has_bom ? 'Yes' : 'No'}</li>
                        ${data.has_bom ? `<li><strong>BOM Cost:</strong> $${data.bom_cost.toFixed(2)}</li>` : ''}
                    </ul>
                </div>
            </div>
        `;
    }

    createDrillDownModal() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'drillDownModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Detail View</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- Content will be populated dynamically -->
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        return modal;
    }

    switchReportTab(reportType) {
        // Update active tab
        document.querySelectorAll('.report-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`[data-report-type="${reportType}"]`)?.classList.add('active');
        
        // Show/hide report sections
        document.querySelectorAll('.report-section').forEach(section => {
            section.style.display = 'none';
        });
        document.getElementById(`${reportType}Report`)?.style.display = 'block';
    }

    async exportReport(format) {
        try {
            const params = this.getDateRangeParams();
            const response = await fetch(`/reports/api/export?format=${format}&${params}`);
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `report_${new Date().toISOString().split('T')[0]}.${format}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showNotification(`Report exported as ${format.toUpperCase()}`, 'success');
            } else {
                this.showNotification('Error exporting report', 'error');
            }
        } catch (error) {
            console.error('Error exporting report:', error);
            this.showNotification('Error exporting report', 'error');
        }
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

// Initialize Enhanced Reports when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('salesChart')) {
        window.enhancedReports = new EnhancedReports();
    }
});