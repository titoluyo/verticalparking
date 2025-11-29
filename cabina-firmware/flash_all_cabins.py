#!/usr/bin/env python3
"""
Batch flash script for programming multiple ESP32 cabins in sequence.

Edit the CABINS list below with your device IDs and ports, then run:
    python flash_all_cabins.py
"""

import subprocess
import sys
from pathlib import Path

# Configure your cabins here: [device_id, port]
CABINS = [
    ["cabin-A01", "COM3"],
    ["cabin-A02", "COM4"],
    ["cabin-A03", "COM5"],
    # Add more cabins as needed
    # ["cabin-A04", "COM6"],
]

def main():
    script_dir = Path(__file__).parent.absolute()
    flash_script = script_dir / "flash_cabin.py"
    
    if not flash_script.exists():
        print(f"ERROR: flash_cabin.py not found at {flash_script}", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Batch Flashing {len(CABINS)} Cabins")
    print(f"{'='*60}\n")
    
    success_count = 0
    fail_count = 0
    
    for i, (device_id, port) in enumerate(CABINS, 1):
        print(f"\n{'#'*60}")
        print(f"# Cabin {i}/{len(CABINS)}: {device_id} on {port}")
        print(f"{'#'*60}\n")
        
        cmd = [sys.executable, str(flash_script), "--device-id", device_id, "--port", port]
        
        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                success_count += 1
                print(f"\n✓ Successfully flashed {device_id}")
            else:
                fail_count += 1
                print(f"\n✗ Failed to flash {device_id}", file=sys.stderr)
        except KeyboardInterrupt:
            print(f"\n\nInterrupted by user. Flashed {success_count} cabins successfully.")
            sys.exit(1)
        except Exception as e:
            fail_count += 1
            print(f"\n✗ Error flashing {device_id}: {e}", file=sys.stderr)
        
        # Small delay between devices
        if i < len(CABINS):
            print("\nWaiting 2 seconds before next device...")
            import time
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"Batch Flash Complete")
    print(f"{'='*60}")
    print(f"Success: {success_count}")
    print(f"Failed:  {fail_count}")
    print(f"{'='*60}\n")
    
    if fail_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()

