#!/usr/bin/env python3
"""Monitor serial output from ESP32-S3 running CircuitPython."""
import serial
import serial.tools.list_ports
import sys

def find_esp32_port():
    """Find ESP32-S3 serial port."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Common ESP32 identifiers
        desc_upper = port.description.upper()
        if any(keyword in desc_upper for keyword in ["ESP32", "SERIAL", "CH340", "CP210", "USB SERIAL", "SILICON LABS"]):
            return port.device
    # If no match, list all available ports
    if ports:
        print("Available serial ports:")
        for port in ports:
            print(f"  {port.device}: {port.description}")
    return None

def monitor():
    port = find_esp32_port()
    if not port:
        print("ESP32-S3 serial port not found. Check USB connection.")
        print("\nMake sure:")
        print("  1. ESP32-S3 is connected via USB")
        print("  2. USB drivers are installed (CH340/CP2102)")
        print("  3. Device is not in use by another program")
        return
    
    print(f"Monitoring {port} at 115200 baud...")
    print("Press Ctrl+C to exit\n")
    print("-" * 60)
    
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        while True:
            if ser.in_waiting:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(line)
                except UnicodeDecodeError:
                    # Skip invalid characters
                    pass
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
    except serial.SerialException as e:
        print(f"\nSerial error: {e}")
        print("Device may have been disconnected.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if 'ser' in locals():
            ser.close()
            print("Serial port closed.")

if __name__ == "__main__":
    try:
        monitor()
    except ImportError:
        print("Error: pyserial not installed.")
        print("Install it with: pip install pyserial")
        sys.exit(1)

