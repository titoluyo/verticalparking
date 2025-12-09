#!/usr/bin/env python3
"""Watch for state changes and alert."""
import time
import sys
import json

# Try requests first, fallback to urllib
try:
    import requests
    USE_REQUESTS = True
except ImportError:
    try:
        from urllib.request import urlopen
        from urllib.error import URLError
        USE_REQUESTS = False
    except ImportError:
        print("Error: Need either 'requests' or 'urllib' module")
        sys.exit(1)

SERVER = "192.168.10.50"
PORT = 5000
BASE_URL = f"http://{SERVER}:{PORT}/api"
INTERVAL = 1  # Check every second

def get_state():
    try:
        if USE_REQUESTS:
            r = requests.get(f"{BASE_URL}/presence", timeout=3)
            r.raise_for_status()
            return r.json()
        else:
            with urlopen(f"{BASE_URL}/presence", timeout=3) as response:
                return json.loads(response.read().decode())
    except Exception as e:
        return None

def get_active_cabin():
    try:
        if USE_REQUESTS:
            r = requests.get(f"{BASE_URL}/active-cabin", timeout=3)
            r.raise_for_status()
            return r.json().get("active_cabin")
        else:
            with urlopen(f"{BASE_URL}/active-cabin", timeout=3) as response:
                data = json.loads(response.read().decode())
                return data.get("active_cabin")
    except:
        return None

last_state = None
last_cabin = None

print("=== WATCHING FOR CHANGES ===")
print("Waiting for vehicle insertion...")
print()

try:
    while True:
        cabin = get_active_cabin()
        state_data = get_state()
        
        if not state_data:
            time.sleep(INTERVAL)
            continue
        
        current_state = state_data.get("state")
        current_message = state_data.get("message")
        entry = state_data.get("entry", {}).get("present")
        full = state_data.get("full", {}).get("present")
        
        # Check for changes
        if last_state != current_state or last_cabin != cabin:
            timestamp = time.strftime("%H:%M:%S")
            if last_state is not None:
                print(f"\n[{timestamp}] *** CHANGE DETECTED ***")
                print(f"    Cabin: {last_cabin} -> {cabin}")
                print(f"    State: {last_state} -> {current_state}")
            else:
                print(f"[{timestamp}] Initial state: Cabin={cabin}, State={current_state}")
            
            print(f"    Message: {current_message}")
            print(f"    Entry: {entry}, Full: {full}")
            print()
            
            # Alert on specific states
            if current_state == "entered":
                print("    >>> VEHICLE FULLY ENTERED - Ready to save! <<<")
            elif current_state == "transitioning":
                print("    >>> VEHICLE ENTERING... <<<")
        
        last_state = current_state
        last_cabin = cabin
        time.sleep(INTERVAL)
        
except KeyboardInterrupt:
    print("\nStopped watching")

