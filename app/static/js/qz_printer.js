// posrss/app/static/js/qz_printer.js - UPDATED FOR INDONESIA WITH IMPROVED CONNECTION

// Konfigurasi QZ Tray
qz.api.setPromiseType(function promise(resolver) { return new Promise(resolver); });

let qzConnection = null;
let connectionAttempts = 0;
const MAX_CONNECTION_ATTEMPTS = 3;

// Improved connection function with retry logic
async function connectToQZ() {
    if (qz.websocket.isActive()) {
        console.log("✅ QZ Tray is already connected.");
        qzConnection = true;
        return Promise.resolve();
    }

    connectionAttempts++;
    console.log(`🔌 Connecting to QZ Tray... (Attempt ${connectionAttempts}/${MAX_CONNECTION_ATTEMPTS})`);
    
    try {
        await qz.websocket.connect({
            retries: 2,
            delay: 1000,
            keepAlive: 30
        });
        console.log("✅ QZ Tray connected successfully!");
        qzConnection = true;
        connectionAttempts = 0; // Reset on success
        return Promise.resolve();
    } catch (err) {
        console.error(`❌ Failed to connect to QZ Tray (Attempt ${connectionAttempts}):`, err);
        qzConnection = false;
        
        if (connectionAttempts < MAX_CONNECTION_ATTEMPTS) {
            console.log(`🔄 Retrying connection in 2 seconds...`);
            await new Promise(resolve => setTimeout(resolve, 2000));
            return connectToQZ(); // Recursive retry
        } else {
            console.error("❌ Max connection attempts reached. QZ Tray may not be running.");
            connectionAttempts = 0; // Reset for next attempt
            throw new Error("Could not connect to QZ Tray. Please make sure it is running and try again.");
        }
    }
}

// Enhanced printer finding with better fallback
async function findPrinter(name = 'receipt') {
    try {
        await connectToQZ();
        const printers = await qz.printers.find();
        console.log("🖨️ Available printers:", printers);
        
        if (printers.length === 0) {
            throw new Error("No printers found on the system");
        }
        
        // Priority order for printer selection
        const searchTerms = [
            name.toLowerCase(),
            'receipt', 'pos', 'thermal', 
            '58mm', '80mm', 'epson', 'star',
            'xprinter', 'citizen', 'bixolon'
        ];
        
        // Try to find specific printer types
        for (const term of searchTerms) {
            const foundPrinter = printers.find(p => 
                p.toLowerCase().includes(term)
            );
            if (foundPrinter) {
                console.log(`✅ Found specific printer: ${foundPrinter}`);
                return foundPrinter;
            }
        }
        
        // Fallback to first available printer
        console.log(`⚠️ No specific receipt printer found, using default: ${printers[0]}`);
        return printers[0];
        
    } catch (err) {
        console.error("❌ Error finding printers:", err);
        throw err;
    }
}

function formatReceiptForQZ(receiptData) {
    console.log("📝 Formatting receipt data:", receiptData);
    
    let data = [];
    
    // Inisialisasi printer
    data.push('\x1B' + '\x40'); // Initialize printer
    
    // Header - Center align
    data.push('\x1B' + '\x61' + '\x31'); // Center align
    data.push('\x1B' + '\x21' + '\x30'); // Double height & width
    data.push(`${receiptData.store_name}\n\n`);
    data.push('\x1B' + '\x21' + '\x00'); // Normal text
    data.push("KreasiPOS powered by KreasiX\n");
    data.push("====================\n\n");

    // Store Info - Left align
    data.push('\x1B' + '\x61' + '\x30'); // Left align
    if (receiptData.store_name) {
        data.push(`${receiptData.store_name}\n`);
    }
    if (receiptData.store_address) {
        data.push(`${receiptData.store_address}\n`);
    }
    if (receiptData.store_phone) {
        data.push(`Tel: ${receiptData.store_phone}\n`);
    }
    data.push('\n');

    // Transaction Info
    data.push(`No: ${receiptData.receipt_number}\n`);
    data.push(`Tanggal: ${receiptData.date}\n`);
    data.push(`Kasir: ${receiptData.cashier}\n`);
    data.push("--------------------------------\n");

    // Items Header
    data.push("Item                Qty   Harga    \n");
    data.push("--------------------------------\n");

    // Items
    receiptData.items.forEach(item => {
        // Format nama item (maksimal 18 karakter)
        let name = item.name;
        if (name.length > 18) {
            name = name.substring(0, 15) + '...';
        }
        
        // Format quantity (3 digit)
        let qty = item.quantity.toString();
        qty = qty.padStart(3, ' ');
        
        // Format harga (8 digit)
        let price = formatNoCurrency(item.unit_price).padStart(8, ' ');
        
        // Format total (9 digit)
        let total = formatNoCurrency(item.total_price).padStart(6, ' ');
        
        let line = `${name.padEnd(18)} ${qty} ${price}\n${total}\n`;
        data.push(line);
    });

    data.push("--------------------------------\n");

    // Totals - Right align
    data.push('\x1B' + '\x61' + '\x32'); // Right align
    data.push(`Subtotal: ${formatCurrency(receiptData.subtotal).padStart(12, ' ')}\n`);
    
    if (receiptData.tax > 0) {
        data.push(`Pajak: ${formatDiskon(receiptData.tax).padStart(15, ' ')}\n`);
    }
    
    if (receiptData.discount > 0) {
        data.push(`Diskon: ${formatCurrency(receiptData.discount).padStart(14, ' ')}\n`);
    }
    
    data.push('\x1B' + '\x21' + '\x18'); // Emphasized text
    data.push(`TOTAL: ${formatCurrency(receiptData.grand_total).padStart(15, ' ')}\n`);
    data.push('\x1B' + '\x21' + '\x00'); // Normal text
    data.push('\n');

    // Payment Info
    data.push('\x1B' + '\x61' + '\x30'); // Left align
    data.push(`Pembayaran: ${receiptData.payment_method.toUpperCase()}\n`);
    
    if (receiptData.payment_method === 'cash') {
        data.push(`Tunai: ${formatCurrency(receiptData.amount_paid)}\n`);
        data.push(`Kembali: ${formatCurrency(receiptData.change)}\n`);
    }
    
    data.push('\n');

    // Customer Info (jika ada)
    if (receiptData.customer_name) {
        data.push(`Pelanggan: ${receiptData.customer_name}\n`);
    }

    // Footer
    data.push('\x1B' + '\x61' + '\x31'); // Center align
    data.push("Terima kasih atas kunjungan Anda!\n");
    data.push("www.kreasipos.com\n\n\n\n");

    // Cut paper
    data.push('\x1D' + '\x56' + '\x41' + '\x00'); // Full cut

    return data;
}

// Helper function untuk format currency Indonesia
function formatCurrency(amount) {
    return 'Rp ' + Math.round(amount).toLocaleString('id-ID');
}

function formatNoCurrency(amount) {
    return '' + Math.round(amount).toLocaleString('id-ID');
}

function formatDiskon(amount) {
    return Math.round(amount).toLocaleString('id-ID')+'%';
}

async function printTestPageWithQZ() {
    console.log("🧪 Starting test print...");
    
    const testData = {
        store_name: 'Toko Contoh',
        store_address: 'Jl. Contoh No. 123',
        store_phone: '(021) 123-4567',
        receipt_number: 'TEST-' + Date.now().toString().slice(-6),
        date: new Date().toLocaleString('id-ID'),
        cashier: 'System',
        items: [
            { name: 'Produk Test 1', quantity: 1, unit_price: 10000, total_price: 10000 },
            { name: 'Produk Test Panjang Nama', quantity: 2, unit_price: 5000, total_price: 10000 }
        ],
        subtotal: 20000,
        tax: 0,
        discount: 0,
        grand_total: 20000,
        payment_method: 'cash',
        amount_paid: 25000,
        change: 5000,
        customer_name: ''
    };

    return await printReceiptWithQZ(testData);
}

// Enhanced print function with better error handling
async function printReceiptWithQZ(receiptData) {
    try {
        console.log("🖨️ Starting print process...");
        
        // Ensure connection is established
        await connectToQZ();
        
        const printerName = await findPrinter();
        
        if (!printerName) {
            console.error("❌ No printer found");
            return { success: false, message: "No printer found. Please check your printer connections." };
        }

        console.log(`🖨️ Using printer: ${printerName}`);
        
        // Create printer config with specific settings for thermal printers
        const config = qz.configs.create(printerName, {
            encoding: 'UTF-8',
            units: 'mm',
            size: { width: 58, height: 200 }, // 58mm thermal paper
            margins: { top: 0, right: 0, bottom: 0, left: 0 }
        });
        
        const data = formatReceiptForQZ(receiptData);
        
        console.log("📤 Sending data to printer...");
        await qz.print(config, data);
        console.log("✅ Receipt sent to printer successfully!");
        
        return { success: true, message: 'Receipt printed successfully.' };

    } catch (err) {
        console.error("❌ Printing failed:", err);
        
        // Reset connection on error for next attempt
        qzConnection = false;
        
        let errorMessage = err.toString();
        if (errorMessage.includes('QZ Tray')) {
            errorMessage = 'Could not connect to QZ Tray. Please make sure it is running and try again.';
        }
        
        return { success: false, message: errorMessage };
    }
}

// Enhanced auto-connect with better error handling
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔌 Auto-connecting to QZ Tray...");
    
    // Try to connect with a delay to ensure page is fully loaded
    setTimeout(async () => {
        try {
            await connectToQZ();
            console.log("✅ QZ Tray connection established on page load");
        } catch (err) {
            console.log("⚠️ QZ Tray not available on page load, will retry when needed");
            // Don't show error immediately, will retry when printing is needed
        }
    }, 1000);
});

// Add connection status check function
function getQZConnectionStatus() {
    return {
        isConnected: qz.websocket.isActive(),
        connectionObject: qzConnection,
        attempts: connectionAttempts
    };
}

// Export functions for global use
window.printReceiptWithQZ = printReceiptWithQZ;
window.printTestPageWithQZ = printTestPageWithQZ;
window.connectToQZ = connectToQZ;
window.getQZConnectionStatus = getQZConnectionStatus;

console.log("🖨️ Enhanced QZ Printer module loaded successfully");