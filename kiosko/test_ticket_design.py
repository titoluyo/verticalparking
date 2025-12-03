#!/usr/bin/env python3
"""
Professional parking ticket design test.
Final design: Corporate with Boxes (modified)
"""
from escpos.printer import Usb
import traceback
import time
import uuid

p = None
try:
    print("=" * 50)
    print("Parking Ticket Design - Final Version")
    print("=" * 50)
    print("Connecting to printer...")
    p = Usb(0x0fe6, 0x811e)
    print("Printer connected successfully\n")

    # Set encoding for Spanish characters
    try:
        p.charcode("CP850")
    except Exception:
        pass

    # Sample data for testing
    cabin_id = "CABINA-01"
    entry_time = time.strftime("%Y-%m-%d %H:%M:%S")
    entry_date = entry_time[:10]
    entry_hour = entry_time[11:19]
    ticket_id = str(uuid.uuid4())[:8].upper()
    qr_data = f"PARKING:{ticket_id}"
    
    # Use 24 characters width for 80mm paper (safe width)
    WIDTH = 24

    print("Printing final design...")
    print("-" * 50)
    
    # Corporate with Boxes (Modified)
    p.text("\n\n")
    p.set(align="center", bold=True, double_width=True)
    p.text("VERTICAL PARKING\n")
    p.set(align="center", bold=True, double_width=False)
    p.text("Estacionamiento\n")  # Shortened to fit 24 chars
    p.text("=" * WIDTH + "\n")
    p.set(align="left", bold=False)
    p.text("+" + "-" * (WIDTH - 2) + "+\n")
    p.text("| TICKET DE INGRESO" + " " * (WIDTH - 20) + "|\n")
    p.text("+" + "-" * (WIDTH - 2) + "+\n")
    p.text(f"| Espacio:  {cabin_id:<{WIDTH-13}} |\n")
    p.text(f"| Fecha:    {entry_date:<{WIDTH-13}} |\n")
    p.text(f"| Hora:     {entry_hour:<{WIDTH-13}} |\n")
    p.text(f"| Ticket:   {ticket_id:<{WIDTH-13}} |\n")
    p.text("+" + "-" * (WIDTH - 2) + "+\n")
    p.text("=" * WIDTH + "\n")
    p.set(align="center")
    p.text("CÓDIGO QR\n")
    p.qr(qr_data, size=10, ec=3)
    p.text("\n")
    p.set(align="center", bold=False)
    p.text("-" * WIDTH + "\n")
    p.set(align="center", bold=True)
    p.text("INSTRUCCIONES\n")
    p.set(align="left", bold=False)
    p.text("1. Conserve este ticket\n")
    p.text("2. Escanea el código QR\n")
    p.text("3. Retire su vehículo\n")
    p.text("-" * WIDTH + "\n")
    p.set(align="center", bold=False)
    p.text("Gracias por usar\n")  # Split into two lines
    p.text("nuestro servicio\n")
    p.text("=" * WIDTH + "\n")
    p.text("\n\n\n")
    p.cut()

    print("Design printed successfully!")

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
finally:
    if p is not None:
        try:
            p.close()
            print("Printer connection closed.")
        except Exception as close_error:
            print(f"Error closing printer: {close_error}")
