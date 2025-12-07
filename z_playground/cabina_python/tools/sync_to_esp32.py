#!/usr/bin/env python3
"""Sync cabina_python files to ESP32-S3 CIRCUITPY drive."""
import os
import shutil
import sys
from pathlib import Path

def find_circuitpy_drive():
    """Find the CIRCUITPY drive on Windows/Linux/Mac."""
    if sys.platform == "win32":
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                try:
                    # Check if CIRCUITPY drive by looking for code.py or boot_out.txt
                    code_py = os.path.join(drive, "code.py")
                    boot_out = os.path.join(drive, "boot_out.txt")
                    if os.path.exists(code_py) or os.path.exists(boot_out):
                        # Verify it's CircuitPython by checking for boot_out.txt
                        if os.path.exists(boot_out):
                            return drive
                except:
                    pass
    else:
        # Linux/Mac: check /media, /Volumes, /mnt
        for mount_point in ["/media", "/Volumes", "/mnt"]:
            if os.path.exists(mount_point):
                try:
                    for item in os.listdir(mount_point):
                        path = os.path.join(mount_point, item)
                        if os.path.isdir(path):
                            boot_out = os.path.join(path, "boot_out.txt")
                            if os.path.exists(boot_out):
                                return path
                except PermissionError:
                    continue
    return None

def sync_files(source_dir, target_dir, files):
    """Copy files from source to target."""
    source = Path(source_dir)
    target = Path(target_dir)
    
    if not target.exists():
        print(f"Error: Target directory {target} does not exist")
        return False
    
    print(f"Syncing to: {target}")
    success = True
    
    for file in files:
        src = source / file
        dst = target / file
        
        if src.exists():
            try:
                shutil.copy2(src, dst)
                print(f"  ✓ {file}")
            except Exception as e:
                print(f"  ✗ {file}: {e}")
                success = False
        else:
            print(f"  ⚠ {file} (not found in source)")
    
    return success

def main():
    # Get the cabina_python directory (parent of tools/)
    script_dir = Path(__file__).parent
    cabina_dir = script_dir.parent
    
    files_to_sync = [
        "code.py",
        "config.py",
        "sensors.py",
        "mqtt_client.py",
        "net.py",
        "settings.toml",
    ]
    
    target = find_circuitpy_drive()
    if not target:
        print("Error: CIRCUITPY drive not found. Connect your ESP32-S3.")
        print("Make sure the device is connected via USB and CircuitPython is installed.")
        sys.exit(1)
    
    print(f"Found CIRCUITPY drive: {target}\n")
    
    if sync_files(cabina_dir, target, files_to_sync):
        print("\n✓ Sync complete! Device will auto-reload.")
        print("Check serial monitor for output.")
    else:
        print("\n✗ Sync completed with errors")
        sys.exit(1)

if __name__ == "__main__":
    main()

