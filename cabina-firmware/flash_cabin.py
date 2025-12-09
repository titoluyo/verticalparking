#!/usr/bin/env python3
"""
Flash script for programming multiple ESP32 cabins with different device IDs.

Usage:
    python flash_cabin.py --device-id cabin-A01 --port COM3
    python flash_cabin.py --device-id cabin-A02 --port COM4 --monitor
"""

import argparse
import re
import subprocess
import sys
import os
from pathlib import Path


def update_sdkconfig(device_id):
    """Update sdkconfig file with new device ID."""
    sdkconfig_path = Path("sdkconfig")
    
    if not sdkconfig_path.exists():
        print(f"ERROR: sdkconfig file not found at {sdkconfig_path.absolute()}", file=sys.stderr)
        return False
    
    # Read current content
    try:
        with open(sdkconfig_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"ERROR: Failed to read sdkconfig: {e}", file=sys.stderr)
        return False
    
    # Replace device ID using regex
    pattern = r'CONFIG_EXAMPLE_MQTT_DEVICE_ID="[^"]*"'
    replacement = f'CONFIG_EXAMPLE_MQTT_DEVICE_ID="{device_id}"'
    
    if re.search(pattern, content):
        new_content = re.sub(pattern, replacement, content)
        print(f"✓ Updated device ID to: {device_id}")
    else:
        # If not found, try to add it (shouldn't happen, but handle gracefully)
        print(f"WARNING: CONFIG_EXAMPLE_MQTT_DEVICE_ID not found in sdkconfig", file=sys.stderr)
        print(f"Attempting to add it...", file=sys.stderr)
        # Try to find the Example Configuration section and add it
        if 'CONFIG_EXAMPLE_MQTT_SITE_ID' in content:
            new_content = re.sub(
                r'(CONFIG_EXAMPLE_MQTT_SITE_ID="[^"]*")',
                rf'\1\n{replacement}',
                content
            )
        else:
            print(f"ERROR: Could not find location to add device ID", file=sys.stderr)
            return False
    
    # Write updated content
    try:
        with open(sdkconfig_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(new_content)
        return True
    except Exception as e:
        print(f"ERROR: Failed to write sdkconfig: {e}", file=sys.stderr)
        return False


def run_command(cmd, description, check=True):
    """Run a shell command and handle errors."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=check, capture_output=False)
        if result.returncode == 0:
            print(f"✓ {description} completed successfully")
            return True
        else:
            print(f"✗ {description} failed with exit code {result.returncode}", file=sys.stderr)
            return False
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed: {e}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"✗ Command not found. Make sure ESP-IDF environment is activated.", file=sys.stderr)
        print(f"  Run: . $IDF_PATH/export.sh (Linux/Mac) or $IDF_PATH/export.ps1 (Windows)", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ {description} failed with error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Flash ESP32 cabin firmware with specified device ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python flash_cabin.py --device-id cabina-01 --port COM3
  python flash_cabin.py --device-id cabina-02 --port COM4 --monitor
  python flash_cabin.py -d cabina-03 -p /dev/ttyUSB0
        """
    )
    
    parser.add_argument(
        '-d', '--device-id',
        required=True,
        help='Device ID (e.g., cabina-01, cabina-02)'
    )
    
    parser.add_argument(
        '-p', '--port',
        required=True,
        help='Serial port (e.g., COM3 on Windows, /dev/ttyUSB0 on Linux)'
    )
    
    parser.add_argument(
        '-m', '--monitor',
        action='store_true',
        help='Start serial monitor after flashing'
    )
    
    parser.add_argument(
        '--skip-build',
        action='store_true',
        help='Skip build step (use existing build)'
    )
    
    args = parser.parse_args()
    
    # Validate device ID format (optional, but helpful)
    if not args.device_id or len(args.device_id) == 0:
        print("ERROR: Device ID cannot be empty", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"ESP32 Cabin Flashing Tool")
    print(f"{'='*60}")
    print(f"Device ID: {args.device_id}")
    print(f"Serial Port: {args.port}")
    print(f"{'='*60}\n")
    
    # Change to script directory (where sdkconfig should be)
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    print(f"Working directory: {script_dir}")
    
    # Step 1: Update sdkconfig
    if not update_sdkconfig(args.device_id):
        print("\n✗ Failed to update sdkconfig", file=sys.stderr)
        sys.exit(1)
    
    # Step 2: Build (unless skipped)
    if not args.skip_build:
        if not run_command(['idf.py', 'build'], 'Building firmware'):
            print("\n✗ Build failed", file=sys.stderr)
            sys.exit(1)
    else:
        print("\n⏭ Skipping build step")
    
    # Step 3: Flash
    flash_cmd = ['idf.py', '-p', args.port, 'flash']
    if not run_command(flash_cmd, f'Flashing to {args.port}'):
        print("\n✗ Flash failed", file=sys.stderr)
        sys.exit(1)
    
    # Step 4: Monitor (if requested)
    if args.monitor:
        print(f"\n{'='*60}")
        print(f"Starting serial monitor (Ctrl+] to exit)")
        print(f"{'='*60}\n")
        monitor_cmd = ['idf.py', '-p', args.port, 'monitor']
        # Monitor runs until user exits, so don't check return code
        subprocess.run(monitor_cmd)
    
    print(f"\n{'='*60}")
    print(f"✓ Successfully programmed {args.device_id} on {args.port}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

