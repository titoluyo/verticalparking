#!/usr/bin/env python3
"""
Comprehensive printer capability test script.
Tests all features of python-escpos and the Cashino KP-300 printer.
"""
from escpos.printer import Usb
import traceback

p = None
try:
    print("=" * 50)
    print("Printer Capability Test")
    print("=" * 50)
    print("Attempting to connect to printer...")
    p = Usb(0x0fe6, 0x811e)
    print("Printer connected successfully\n")

    # Test 1: Basic Text
    print("[TEST 1] Basic Text")
    p.text("=" * 32 + "\n")
    p.text("TEST 1: Basic Text\n")
    p.text("This is normal text.\n")
    p.text("=" * 32 + "\n\n")

    # Test 2: Fonts
    print("[TEST 2] Fonts")
    p.text("=" * 32 + "\n")
    p.text("TEST 2: Fonts\n")
    try:
        p.set(font="a")
        p.text("Font A (default)\n")
    except Exception as e:
        p.text(f"Font A failed: {e}\n")
    
    try:
        p.set(font="b")
        p.text("Font B\n")
    except Exception as e:
        p.text(f"Font B failed: {e}\n")
    
    try:
        p.set(font="c")
        p.text("Font C\n")
    except Exception as e:
        p.text(f"Font C failed: {e}\n")
    
    p.set(font="a")  # Reset to default
    p.text("=" * 32 + "\n\n")

    # Test 3: Text Styles
    print("[TEST 3] Text Styles")
    p.text("=" * 32 + "\n")
    p.text("TEST 3: Text Styles\n")
    
    try:
        p.set(bold=True)
        p.text("Bold text\n")
        p.set(bold=False)
    except Exception as e:
        p.text(f"Bold failed: {e}\n")
    
    try:
        p.set(underline=1)
        p.text("Underlined text\n")
        p.set(underline=0)
    except Exception as e:
        p.text(f"Underline failed: {e}\n")
    
    try:
        p.set(double_width=True)
        p.text("Double width\n")
        p.set(double_width=False)
    except Exception as e:
        p.text(f"Double width failed: {e}\n")
    
    try:
        p.set(double_height=True)
        p.text("Double height\n")
        p.set(double_height=False)
    except Exception as e:
        p.text(f"Double height failed: {e}\n")
    
    try:
        p.set(double_width=True, double_height=True)
        p.text("Double width + height\n")
        p.set(double_width=False, double_height=False)
    except Exception as e:
        p.text(f"Double width+height failed: {e}\n")
    
    p.text("=" * 32 + "\n\n")

    # Test 4: Alignment
    print("[TEST 4] Alignment")
    p.text("=" * 32 + "\n")
    p.text("TEST 4: Alignment\n")
    
    try:
        p.set(align="left")
        p.text("Left aligned text\n")
    except Exception as e:
        p.text(f"Left align failed: {e}\n")
    
    try:
        p.set(align="center")
        p.text("Center aligned\n")
    except Exception as e:
        p.text(f"Center align failed: {e}\n")
    
    try:
        p.set(align="right")
        p.text("Right aligned\n")
    except Exception as e:
        p.text(f"Right align failed: {e}\n")
    
    p.set(align="left")  # Reset
    p.text("=" * 32 + "\n\n")

    # Test 5: Character Encodings
    print("[TEST 5] Character Encodings")
    p.text("=" * 32 + "\n")
    p.text("TEST 5: Character Encodings\n")
    
    try:
        p.charcode("PC437")
        p.text("PC437: Hello World!\n")
    except Exception as e:
        p.text(f"PC437 failed: {e}\n")
    
    try:
        p.charcode("LATIN1")
        p.text("LATIN1: Café, résumé\n")
    except Exception as e:
        p.text(f"LATIN1 failed: {e}\n")
    
    try:
        p.charcode("CP850")
        p.text("CP850: Español, ñoño\n")
    except Exception as e:
        p.text(f"CP850 failed: {e}\n")
    
    p.text("=" * 32 + "\n\n")

    # Test 6: QR Codes - Different Sizes
    print("[TEST 6] QR Codes - Sizes")
    p.text("=" * 32 + "\n")
    p.text("TEST 6: QR Codes - Sizes\n")
    
    sizes = [4, 6, 8, 10]
    for size in sizes:
        try:
            p.text(f"QR Size {size}:\n")
            p.qr("https://github.com/verticalparking", size=size, ec=0)
            p.text("\n")
        except Exception as e:
            p.text(f"QR size {size} failed: {e}\n")
    
    p.text("=" * 32 + "\n\n")

    # Test 7: QR Codes - Error Correction Levels
    print("[TEST 7] QR Codes - Error Correction")
    p.text("=" * 32 + "\n")
    p.text("TEST 7: QR Error Correction\n")
    
    ec_levels = [0, 1, 2, 3]  # L, M, Q, H
    ec_names = ["L (Low)", "M (Medium)", "Q (Quartile)", "H (High)"]
    for ec, name in zip(ec_levels, ec_names):
        try:
            p.text(f"QR EC {name}:\n")
            p.qr("TEST-12345", size=6, ec=ec)
            p.text("\n")
        except Exception as e:
            p.text(f"QR EC {ec} failed: {e}\n")
    
    p.text("=" * 32 + "\n\n")

    # Test 8: Barcodes
    print("[TEST 8] Barcodes")
    p.text("=" * 32 + "\n")
    p.text("TEST 8: Barcodes\n")
    
    barcode_types = [
        ("EAN13", "123456789012"),
        ("EAN8", "12345670"),
        ("CODE39", "TEST123"),
        ("ITF", "1234567890"),
        ("CODE128", "TEST-12345"),
    ]
    
    for btype, data in barcode_types:
        try:
            p.text(f"{btype}:\n")
            p.barcode(data, btype, height=50, width=2, pos="BELOW", font="A")
            p.text("\n")
        except Exception as e:
            p.text(f"{btype} failed: {e}\n")
    
    p.text("=" * 32 + "\n\n")

    # Test 9: Line Spacing
    print("[TEST 9] Line Spacing")
    p.text("=" * 32 + "\n")
    p.text("TEST 9: Line Spacing\n")
    
    try:
        p.text("Normal spacing:\n")
        p.text("Line 1\n")
        p.text("Line 2\n")
    except Exception as e:
        p.text(f"Normal spacing failed: {e}\n")
    
    try:
        p.text("Custom spacing (30):\n")
        p.line_spacing(30)
        p.text("Line 1\n")
        p.text("Line 2\n")
        p.line_spacing()  # Reset to default
    except Exception as e:
        p.text(f"Custom spacing failed: {e}\n")
    
    p.text("=" * 32 + "\n\n")

    # Test 10: Cut Types
    print("[TEST 10] Cut Types")
    p.text("=" * 32 + "\n")
    p.text("TEST 10: Cut Types\n")
    p.text("Testing different cut types...\n")
    p.text("(Check if paper was cut)\n")
    p.text("=" * 32 + "\n\n")

    # Test 11: Combined Formatting
    print("[TEST 11] Combined Formatting")
    p.text("=" * 32 + "\n")
    p.text("TEST 11: Combined\n")
    
    try:
        p.set(align="center", bold=True, double_width=True)
        p.text("CENTER BOLD LARGE\n")
        p.set(align="left", bold=False, double_width=False)
    except Exception as e:
        p.text(f"Combined formatting failed: {e}\n")
    
    p.text("=" * 32 + "\n\n")

    # Test 12: Special Characters
    print("[TEST 12] Special Characters")
    p.text("=" * 32 + "\n")
    p.text("TEST 12: Special Chars\n")
    p.text("Spanish: á é í ó ú ñ\n")
    p.text("Symbols: © ® ™ € £ ¥\n")
    p.text("Math: ± × ÷ ≠ ≤ ≥\n")
    p.text("=" * 32 + "\n\n")

    # Test 13: Paper Feed
    print("[TEST 13] Paper Feed")
    p.text("=" * 32 + "\n")
    p.text("TEST 13: Paper Feed\n")
    
    try:
        p.text("Before feed\n")
        p.control("LF")  # Line feed
        p.text("After feed\n")
    except Exception as e:
        p.text(f"Paper feed failed: {e}\n")
    
    p.text("=" * 32 + "\n\n")

    # Final summary
    p.text("=" * 32 + "\n")
    p.text("TEST COMPLETE\n")
    p.text("Review printed output above\n")
    p.text("=" * 32 + "\n")
    p.text("\n\n")

    print("All tests completed. Cutting paper...")
    try:
        p.cut()
    except Exception as e:
        print(f"Cut failed: {e}")
        p.text("\n\n\n")  # Feed paper instead
    
    print("Print test successful!")

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
