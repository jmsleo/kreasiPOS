import logging
from flask import current_app
import socket

logger = logging.getLogger(__name__)

class PrinterService:
    def __init__(self):
        self.printer_ip = current_app.config.get('PRINTER_IP')
        self.printer_port = current_app.config.get('PRINTER_PORT', 9100)
    
    def print_receipt(self, receipt_data):
        """Print receipt to network thermal printer"""
        try:
            if not self.printer_ip:
                logger.error("Printer IP not configured")
                return False
            
            # Create socket connection to printer
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.printer_ip, self.printer_port))
            
            # ESC/POS commands for receipt formatting
            esc_pos_commands = self._format_receipt(receipt_data)
            
            # Send commands to printer
            sock.send(esc_pos_commands)
            sock.close()
            
            logger.info("Receipt printed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to print receipt: {str(e)}")
            return False
    
    def _format_receipt(self, receipt_data):
        """Format receipt data into ESC/POS commands"""
        # Initialize with reset command
        commands = b'\x1B@'
        
        # Company header
        commands += b'\x1B\x61\x01'  # Center alignment
        commands += b'\x1B\x21\x30'  # Double height and width
        commands += f"{receipt_data.get('company_name', 'T-POS ENTERPRISE')}\n".encode('utf-8')
        
        # Reset text size
        commands += b'\x1B\x21\x00'
        commands += f"{receipt_data.get('store_name', '')}\n".encode('utf-8')
        commands += f"{receipt_data.get('store_address', '')}\n".encode('utf-8')
        commands += f"Tel: {receipt_data.get('store_phone', '')}\n\n".encode('utf-8')
        
        # Left alignment for items
        commands += b'\x1B\x61\x00'
        
        # Receipt info
        commands += f"Receipt: {receipt_data.get('receipt_number', '')}\n".encode('utf-8')
        commands += f"Date: {receipt_data.get('date', '')}\n".encode('utf-8')
        commands += f"Cashier: {receipt_data.get('cashier', '')}\n\n".encode('utf-8')
        
        # Items header
        commands += b'\x1B\x45\x01'  # Bold on
        commands += "ITEM".ljust(20).encode('utf-8')
        commands += "QTY".center(5).encode('utf-8')
        commands += "PRICE".rjust(10).encode('utf-8')
        commands += "TOTAL".rjust(10).encode('utf-8') + b'\n'
        commands += b'\x1B\x45\x00'  # Bold off
        
        # Items
        for item in receipt_data.get('items', []):
            name = item.get('name', '')[:18] + '..' if len(item.get('name', '')) > 18 else item.get('name', '')
            commands += f"{name}".ljust(20).encode('utf-8')
            commands += f"{item.get('quantity', 0)}".center(5).encode('utf-8')
            commands += f"{item.get('price', 0):.2f}".rjust(10).encode('utf-8')
            commands += f"{item.get('total', 0):.2f}".rjust(10).encode('utf-8') + b'\n'
        
        # Separator
        commands += b'-' * 48 + b'\n'
        
        # Totals
        commands += b'\x1B\x45\x01'  # Bold on
        commands += f"TOTAL: {receipt_data.get('grand_total', 0):.2f}\n".encode('utf-8')
        commands += b'\x1B\x45\x00'  # Bold off
        
        # Payment info
        commands += f"Payment: {receipt_data.get('payment_method', '').upper()}\n".encode('utf-8')
        commands += f"Amount Paid: {receipt_data.get('amount_paid', 0):.2f}\n".encode('utf-8')
        commands += f"Change: {receipt_data.get('change', 0):.2f}\n\n".encode('utf-8')
        
        # Footer
        commands += b'\x1B\x61\x01'  # Center alignment
        commands += "Thank you for your business!\n".encode('utf-8')
        commands += "Please come again!\n\n".encode('utf-8')
        
        # Cut paper (partial cut)
        commands += b'\x1D\x56\x41\x10'
        
        return commands
    
    def test_connection(self):
        """Test printer connection"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.printer_ip, self.printer_port))
            sock.close()
            return True
        except Exception as e:
            logger.error(f"Printer connection test failed: {str(e)}")
            return False