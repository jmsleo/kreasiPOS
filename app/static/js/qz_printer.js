// posrss/app/static/js/qz_printer.js

// Konfigurasi QZ Tray
qz.api.setPromiseType(function promise(resolver) { return new Promise(resolver); });

let qzConnection = null;

async function connectToQZ() {
    if (qz.websocket.isActive()) {
        console.log("QZ Tray is already connected.");
        return Promise.resolve();
    }
    try {
        console.log("Connecting to QZ Tray...");
        await qz.websocket.connect();
        console.log("QZ Tray connected successfully!");
        qzConnection = true;
    } catch (err) {
        console.error("Failed to connect to QZ Tray:", err);
        alert("Could not connect to QZ Tray. Please make sure it is running.");
        qzConnection = false;
        return Promise.reject(err);
    }
}

async function findPrinter(name = 'receipt') {
    await connectToQZ();
    try {
        const printers = await qz.printers.find();
        // Coba cari printer yang mengandung kata 'receipt', 'pos', 'thermal'
        const foundPrinter = printers.find(p => p.toLowerCase().includes(name) || p.toLowerCase().includes('pos') || p.toLowerCase().includes('thermal'));
        if (foundPrinter) {
            console.log(`Printer found: ${foundPrinter}`);
            return foundPrinter;
        } else {
            console.log("No specific receipt printer found, using default.");
            return printers[0]; // Gunakan printer pertama jika tidak ditemukan
        }
    } catch (err) {
        console.error("Error finding printers:", err);
        return Promise.reject(err);
    }
}

function formatReceiptForQZ(receiptData) {
    // Fungsi ini mengubah data struk JSON menjadi format ESC/POS
    let data = [];
    
    // Inisialisasi printer
    data.push('\x1B' + '\x40'); 
    
    // Header
    data.push('\x1B' + '\x61' + '\x31'); // Center align
    data.push('\x1B' + '\x21' + '\x30'); // Double height & width
    data.push(receiptData.company_name + '\n');
    data.push('\x1B' + '\x21' + '\x00'); // Normal text
    data.push(receiptData.store_address + '\n');
    data.push(`Tel: ${receiptData.store_phone}\n\n`);

    // Info
    data.push('\x1B' + '\x61' + '\x30'); // Left align
    data.push(`Receipt: ${receiptData.receipt_number}\n`);
    data.push(`Date: ${receiptData.date}\n`);
    data.push(`Cashier: ${receiptData.cashier}\n\n`);

    // Items
    receiptData.items.forEach(item => {
        let name = item.name.substring(0, 20); // Potong nama item jika terlalu panjang
        let qty = item.quantity.toString();
        let price = `$${item.price.toFixed(2)}`;
        let total = `$${item.total.toFixed(2)}`;
        let line = `${name.padEnd(20)} ${qty.padStart(3)} ${price.padStart(8)} ${total.padStart(8)}\n`;
        data.push(line);
    });

    data.push('-'.repeat(42) + '\n');

    // Totals
    data.push('\x1B' + '\x61' + '\x32'); // Right align
    data.push(`Subtotal: $${receiptData.subtotal.toFixed(2)}\n`);
    data.push(`Tax: $${receiptData.tax.toFixed(2)}\n`);
    if(receiptData.discount > 0) {
        data.push(`Discount: -$${receiptData.discount.toFixed(2)}\n`);
    }
    data.push('\x1B' + '\x21' + '\x18'); // Emphasized text
    data.push(`TOTAL: $${receiptData.grand_total.toFixed(2)}\n`);
    data.push('\x1B' + '\x21' + '\x00'); // Normal text

    // Payment
    data.push(`Payment: ${receiptData.payment_method}\n`);
    data.push(`Amount Paid: $${receiptData.amount_paid.toFixed(2)}\n`);
    data.push(`Change: $${receiptData.change.toFixed(2)}\n\n`);


    // Footer
    data.push('\x1B' + '\x61' + '\x31'); // Center align
    data.push('Thank you for your business!\n\n\n');

    // Cut paper
    data.push('\x1D' + '\x56' + '\x41' + '\x00');

    return data;
}

async function printTestPageWithQZ() {
    console.log("Starting test print...");
    // 1. Buat data struk palsu untuk tes
    const testData = {
        company_name: 'KreasiPOS Enterprise',
        store_address: 'Test Print Successful!',
        store_phone: new Date().toLocaleString(),
        receipt_number: 'TEST-001',
        date: '',
        cashier: 'System',
        items: [
            { name: 'Test Item 1', quantity: 1, price: 10.00, total: 10.00 },
            { name: 'Test Item 2', quantity: 2, price: 5.00, total: 10.00 }
        ],
        subtotal: 20.00,
        tax: 2.00,
        discount: 0.00,
        grand_total: 22.00,
        payment_method: 'CASH',
        amount_paid: 30.00,
        change: 8.00
    };

    // 2. Panggil fungsi cetak yang sudah ada
    // Kita menggunakan kembali logika yang sama untuk mencetak struk asli
    return await printReceiptWithQZ(testData);
}


async function printReceiptWithQZ(receiptData) {
    try {
        const printerName = await findPrinter();
        if (!printerName) {
            alert("No printer found. Please check your printer connections.");
            return;
        }

        const config = qz.configs.create(printerName);
        const data = formatReceiptForQZ(receiptData);
        
        console.log("Sending data to printer:", data);
        await qz.print(config, data);
        console.log("Receipt sent to printer successfully!");
        return { success: true, message: 'Receipt sent to printer.' };

    } catch (err) {
        console.error("Printing failed:", err);
        return { success: false, message: err.toString() };
    }
}