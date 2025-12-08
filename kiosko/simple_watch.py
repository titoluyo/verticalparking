#!/usr/bin/env python3
"""Simple watch script using only standard library."""
import urllib.request
import json
import time
import sys

BASE_URL = "http://192.168.10.50:5000/api"

def get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return None

print("=== WATCHING FOR CHANGES ===")
print("Current state:")
print()

last_state = None
last_cabin = None

try:
    while True:
        # Get active cabin
        active_data = get_json(f"{BASE_URL}/active-cabin")
        cabin = active_data.get("active_cabin") if active_data else None
        
        # Get presence
        presence = get_json(f"{BASE_URL}/presence")
        if not presence:
            time.sleep(1)
            continue
        
        state = presence.get("state")
        message = presence.get("message")
        entry = presence.get("entry", {}).get("present")
        full = presence.get("full", {}).get("present")
        
        # Show change
        if last_state != state or last_cabin != cabin:
            timestamp = time.strftime("%H:%M:%S")
            if last_state is not None:
                print(f"\n[{timestamp}] *** CHANGE ***")
                if last_cabin != cabin:
                    print(f"  Cabin: {last_cabin} -> {cabin}")
                if last_state != state:
                    print(f"  State: {last_state} -> {state}")
            else:
                print(f"[{timestamp}] Initial: Cabin={cabin}, State={state}")
            
            print(f"  Message: {message}")
            print(f"  Entry: {entry}, Full: {full}")
            
            if state == "entered":
                print("  >>> VEHICLE ENTERED - SAVE NOW! <<<")
            elif state == "transitioning":
                print("  >>> VEHICLE ENTERING... <<<")
            
            sys.stdout.flush()
        
        last_state = state
        last_cabin = cabin
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\nStopped")
