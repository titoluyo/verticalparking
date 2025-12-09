#!/usr/bin/env python3
"""
Build multiple firmware binaries with different device IDs hardcoded.

This script builds separate firmware binaries for each device ID.
Each binary will have the device ID compiled into it.

Usage:
    python build_multi_firmware.py --device-ids cabina-01 cabina-02 cabina-03
    python build_multi_firmware.py --all  # Build for all default device IDs

    If you get "idf.py not found", activate the ESP-IDF environment first:
    pwsh.exe -ExecutionPolicy Bypass -NoExit -File "C:\Espressif/Initialize-Idf.ps1" -IdfId esp-idf-29323a3f5a0574597d6dbaa0af20c775
"""

import argparse
import subprocess
import sys
import os
import re
import shutil
from pathlib import Path


# Default device IDs
DEFAULT_DEVICE_IDS = [
    "cabina-00",
    "cabina-01",
    "cabina-02",
    "cabina-03",
    "cabina-04",
    "cabina-05",
    "cabina-06",
]


def update_sdkconfig(device_id: str, sdkconfig_path: Path) -> bool:
    """Update sdkconfig with device ID."""
    try:
        with open(sdkconfig_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        pattern = r'CONFIG_EXAMPLE_MQTT_DEVICE_ID="[^"]*"'
        replacement = f'CONFIG_EXAMPLE_MQTT_DEVICE_ID="{device_id}"'
        
        if re.search(pattern, content):
            new_content = re.sub(pattern, replacement, content)
            with open(sdkconfig_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(new_content)
            return True
        else:
            print(f"  ⚠ CONFIG_EXAMPLE_MQTT_DEVICE_ID not found in sdkconfig", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  ✗ Failed to update sdkconfig: {e}", file=sys.stderr)
        return False


def build_firmware(device_id: str, output_dir: Path, clean: bool = False) -> bool:
    """Build firmware for a specific device ID."""
    print(f"\n{'='*60}")
    print(f"Building firmware for: {device_id}")
    print(f"{'='*60}")
    
    sdkconfig_path = Path("sdkconfig")
    build_dir = Path("build")
    firmware_bin = build_dir / "cabina-firmware.bin"
    
    # Step 1: Update sdkconfig
    print(f"1. Updating sdkconfig with device ID: {device_id}")
    if not update_sdkconfig(device_id, sdkconfig_path):
        return False
    
    # Step 2: Clean build if requested
    if clean:
        print(f"2. Cleaning build directory...")
        if build_dir.exists():
            shutil.rmtree(build_dir)
    
    # Step 3: Build
    print(f"3. Building firmware...")
    try:
        import platform
        import shutil
        
        # On Windows, idf.py is typically a batch file that needs shell=True
        if platform.system() == 'Windows':
            # Check if idf.py exists in PATH
            idf_py = shutil.which('idf.py')
            if not idf_py:
                raise FileNotFoundError("idf.py not found in PATH. Please activate ESP-IDF environment first.")
            
            # On Windows, use shell=True to run batch files properly
            result = subprocess.run(
                'idf.py build',
                check=True,
                capture_output=True,
                text=True,
                shell=True
            )
        else:
            # Linux/Mac: direct execution
            result = subprocess.run(
                ['idf.py', 'build'],
                check=True,
                capture_output=True,
                text=True
            )
        print(f"  ✓ Build successful")
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Build failed: {e}", file=sys.stderr)
        if e.stderr:
            print(f"  Build error output:\n{e.stderr}", file=sys.stderr)
        if e.stdout:
            print(f"  Build output:\n{e.stdout}", file=sys.stderr)
        return False
    except FileNotFoundError as e:
        print(f"  ✗ {e}", file=sys.stderr)
        print(f"  Please activate ESP-IDF environment first:", file=sys.stderr)
        print(f"    Windows: Run ESP-IDF PowerShell or cmd prompt", file=sys.stderr)
        print(f"    Or run: pwsh.exe -ExecutionPolicy Bypass -NoExit -File \"C:\\Espressif\\Initialize-Idf.ps1\"", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  ✗ Build failed with error: {e}", file=sys.stderr)
        return False
    
    # Step 4: Copy firmware to output directory
    if not firmware_bin.exists():
        print(f"  ✗ Firmware binary not found at {firmware_bin}", file=sys.stderr)
        return False
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"cabina-firmware-{device_id}.bin"
    
    try:
        shutil.copy2(firmware_bin, output_file)
        file_size = output_file.stat().st_size
        print(f"4. Copied firmware to: {output_file}")
        print(f"   Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to copy firmware: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Build multiple firmware binaries with different device IDs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build for specific devices
  python build_multi_firmware.py --device-ids cabina-01 cabina-02
  
  # Build for all default devices
  python build_multi_firmware.py --all
  
  # Build with clean build
  python build_multi_firmware.py --all --clean
        """
    )
    
    parser.add_argument(
        '--device-ids',
        nargs='+',
        help='Device IDs to build (e.g., cabina-01 cabina-02)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Build for all default device IDs'
    )
    
    parser.add_argument(
        '--output-dir',
        default='firmware_builds',
        help='Output directory for firmware binaries (default: firmware_builds)'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean build directory before each build'
    )
    
    args = parser.parse_args()
    
    # Determine device IDs
    if args.all:
        device_ids = DEFAULT_DEVICE_IDS
    elif args.device_ids:
        device_ids = args.device_ids
    else:
        print("ERROR: Must specify --device-ids or --all", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Multi-Firmware Builder")
    print(f"{'='*60}")
    print(f"Device IDs: {', '.join(device_ids)}")
    print(f"Output directory: {args.output_dir}")
    print(f"{'='*60}\n")
    
    # Change to script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build firmware for each device
    success_count = 0
    fail_count = 0
    
    for device_id in device_ids:
        if build_firmware(device_id, output_dir, args.clean):
            success_count += 1
        else:
            fail_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Build Summary")
    print(f"{'='*60}")
    print(f"Success: {success_count}")
    print(f"Failed:  {fail_count}")
    print(f"Output directory: {output_dir.absolute()}")
    print(f"{'='*60}\n")
    
    if fail_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()

