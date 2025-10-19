class Dashboard {
    constructor() {
        this.charts = {};
        this.init();
    }

    init() {
        this.loadSalesData();
        this.loadTopProducts();
        this.loadRecentActivity();
        this.bindEvents();
    }

    bindEvents() {
        // Refresh data every 5 minutes
        setInterval(() => {
            this.loadSalesData();
            this.loadTopProducts();
        }, 300000);

        // Date range filters
        const dateFilter = document.getElementById('dateFilter');
        if (dateFilter) {
            dateFilter.addEventListener('change', () => {
                this.loadSalesData();
            });
        }
    }

    async loadSalesData() {
        try {
            const response = await fetch('/dashboard/sales-data');
            const data = await response.json();
            
            this.renderSalesChart(data);
            this.renderRevenueChart(data);
        } catch (error) {
            console.error('Error loading sales data:', error);
        }
    }

    renderSalesChart(data) {
        const ctx = document.getElementById('salesChart');
        if (!ctx) return;

        if (this.charts.sales) {
            this.charts.sales.destroy();
        }

        this.charts.sales = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.dates,
                datasets: [{
                    label: 'Daily Revenue',
                    data: data.revenues,
                    borderColor: '#4e73df',
                    backgroundColor: 'rgba(78, 115, 223, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Daily Sales Revenue'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    }

    renderRevenueChart(data) {
        const ctx = document.getElementById('revenueChart');
        if (!ctx) return;

        if (this.charts.revenue) {
            this.charts.revenue.destroy();
        }

        this.charts.revenue = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.dates,
                datasets: [{
                    label: 'Transactions',
                    data: data.transactions,
                    backgroundColor: '#1cc88a',
                    borderColor: '#1cc88a',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Daily Transactions'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    async loadTopProducts() {
        try {
            const response = await fetch('/dashboard/top-products');
            const products = await response.json();
            
            this.renderTopProducts(products);
        } catch (error) {
            console.error('Error loading top products:', error);
        }
    }

    renderTopProducts(products) {
        const container = document.getElementById('topProducts');
        if (!container) return;

        if (products.length === 0) {
            container.innerHTML = '<p class="text-muted">No sales data available</p>';
            return;
        }

        const html = products.map((product, index) => `
            <div class="activity-item">
                <div class="activity-icon product">
                    <i class="bi bi-trophy"></i>
                </div>
                <div class="activity-content">
                    <div class="fw-bold">${product.name}</div>
                    <div class="text-muted small">
                        Sold: ${product.sold} units | Revenue: $${product.revenue.toFixed(2)}
                    </div>
                </div>
                <div class="badge bg-primary">#${index + 1}</div>
            </div>
        `).join('');

        container.innerHTML = html;
    }

    async loadRecentActivity() {
        try {
            const response = await fetch('/dashboard/recent-activity');
            const activities = await response.json();
            
            this.renderRecentActivity(activities);
        } catch (error) {
            console.error('Error loading recent activity:', error);
        }
    }

    renderRecentActivity(activities) {
        const container = document.getElementById('recentActivity');
        if (!container) return;

        if (activities.length === 0) {
            container.innerHTML = '<p class="text-muted">No recent activity</p>';
            return;
        }

        const html = activities.map(activity => `
            <div class="activity-item">
                <div class="activity-icon ${activity.type}">
                    <i class="bi ${activity.icon}"></i>
                </div>
                <div class="activity-content">
                    <div class="fw-bold">${activity.title}</div>
                    <div class="text-muted small">${activity.description}</div>
                </div>
                <div class="activity-time">${activity.time}</div>
            </div>
        `).join('');

        container.innerHTML = html;
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', function() {
    window.dashboard = new Dashboard();
});