// Chart configuration and utilities
const ChartConfig = {
    colors: {
        primary: '#4e73df',
        success: '#1cc88a',
        info: '#36b9cc',
        warning: '#fd7e14',
        danger: '#e74a3b',
        secondary: '#858796',
        light: '#f8f9fc',
        dark: '#5a5c69'
    },

    getColorPalette: function(count) {
        const palette = [
            this.primary,
            this.success,
            this.info,
            this.warning,
            this.danger,
            this.secondary,
            '#6f42c1',
            '#e83e8c',
            '#fd7e14',
            '#20c997'
        ];
        return palette.slice(0, count);
    },

    defaultOptions: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: {
                    padding: 20,
                    usePointStyle: true
                }
            }
        }
    }
};

// Sales report charts
class SalesCharts {
    constructor() {
        this.charts = {};
    }

    renderWeeklySales(data) {
        const ctx = document.getElementById('weeklySalesChart');
        if (!ctx) return;

        if (this.charts.weekly) {
            this.charts.weekly.destroy();
        }

        this.charts.weekly = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Sales Revenue',
                    data: data.values,
                    backgroundColor: ChartConfig.colors.primary,
                    borderColor: ChartConfig.colors.primary,
                    borderWidth: 1
                }]
            },
            options: {
                ...ChartConfig.defaultOptions,
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

    renderMonthlySales(data) {
        const ctx = document.getElementById('monthlySalesChart');
        if (!ctx) return;

        if (this.charts.monthly) {
            this.charts.monthly.destroy();
        }

        this.charts.monthly = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Daily Revenue',
                    data: data.values,
                    borderColor: ChartConfig.colors.success,
                    backgroundColor: 'rgba(28, 200, 138, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                ...ChartConfig.defaultOptions,
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

    renderProductPerformance(products) {
        const ctx = document.getElementById('productPerformanceChart');
        if (!ctx) return;

        if (this.charts.products) {
            this.charts.products.destroy();
        }

        const labels = products.map(p => p.name);
        const salesData = products.map(p => p.sold);
        const revenueData = products.map(p => p.revenue);

        this.charts.products = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Units Sold',
                        data: salesData,
                        backgroundColor: ChartConfig.colors.info,
                        borderColor: ChartConfig.colors.info,
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Revenue',
                        data: revenueData,
                        backgroundColor: ChartConfig.colors.warning,
                        borderColor: ChartConfig.colors.warning,
                        borderWidth: 1,
                        yAxisID: 'y1',
                        type: 'line'
                    }
                ]
            },
            options: {
                ...ChartConfig.defaultOptions,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Units Sold'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Revenue ($)'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
    }

    renderPaymentMethods(data) {
        const ctx = document.getElementById('paymentMethodsChart');
        if (!ctx) return;

        if (this.charts.payments) {
            this.charts.payments.destroy();
        }

        this.charts.payments = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    backgroundColor: ChartConfig.getColorPalette(data.labels.length),
                    borderWidth: 1
                }]
            },
            options: {
                ...ChartConfig.defaultOptions,
                cutout: '60%'
            }
        });
    }

    destroyAll() {
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.charts = {};
    }
}

// Initialize charts when needed
document.addEventListener('DOMContentLoaded', function() {
    window.salesCharts = new SalesCharts();
    
    // Auto-resize charts on window resize
    window.addEventListener('resize', function() {
        if (window.salesCharts) {
            // Re-render all charts on resize
            Object.values(window.salesCharts.charts).forEach(chart => {
                if (chart && typeof chart.resize === 'function') {
                    chart.resize();
                }
            });
        }
    });
});