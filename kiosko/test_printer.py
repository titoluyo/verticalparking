from escpos.printer import Usb
import traceback

p = None
try:
    print("Attempting to connect to printer...")
    p = Usb(0x0fe6, 0x811e)
    print("Printer connected successfully")

    print("Sending test text...")
    p.text("Direct test from Python\n")
    p.text("This is a test\n")
    p.text("\n")

    print("Printing QR code...")
    p.text("QR Code Test:\n")
    # Print QR code with URL
    p.qr("https://github.com/verticalparking", size=8, ec=0)
    p.text("\n")
    
    # Print QR code with text
    p.text("QR Code (Text):\n")
    p.qr("PARKING-TICKET-12345", size=6, ec=0)
    p.text("\n")

    print("Attempting to cut paper...")
    p.cut()
    print("Print successful !")
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
