#!/usr/bin/env python3
"""Simple monitoring script for presence service."""
import requests
import time
import json
import sys

SERVER = "192.168.10.50"
PORT = 5000
BASE_URL = f"http://{SERVER}:{PORT}/api"
INTERVAL = 2

def get_active_cabin():
    try:
        r = requests.get(f"{BASE_URL}/active-cabin", timeout=3)
        r.raise_for_status()
        return r.json().get("active_cabin")
    except Exception as e:
        print(f"Error getting active cabin: {e}")
        return None

def get_presence():
    try:
        r = requests.get(f"{BASE_URL}/presence", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error getting presence: {e}")
        return None

def get_debug_cabin(cabin_id):
    try:
        r = requests.get(f"{BASE_URL}/presence/debug/cabin/{cabin_id}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error getting debug info: {e}")
        return None

def main():
    print("=== Monitoring Presence Service ===")
    print(f"Base URL: {BASE_URL}")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        while True:
            timestamp = time.strftime("%H:%M:%S")
            
            # Get active cabin
            active_cabin = get_active_cabin()
            if not active_cabin:
                print(f"[{timestamp}] Error: Could not get active cabin")
                time.sleep(INTERVAL)
                continue
            
            # Get presence status
            presence = get_presence()
            if not presence:
                print(f"[{timestamp}] Error: Could not get presence")
                time.sleep(INTERVAL)
                continue
            
            state = presence.get("state", "unknown")
            message = presence.get("message", "")
            entry = presence.get("entry", {}).get("present", False)
            full = presence.get("full", {}).get("present", False)
            
            # Color coding
            color_code = ""
            if state == "entered":
                color_code = "\033[92m"  # Green
            elif state == "free":
                color_code = "\033[97m"  # White
            else:
                color_code = "\033[93m"  # Yellow
            
            reset_code = "\033[0m"
            
            print(f"{color_code}[{timestamp}] Active: {active_cabin} | State: {state} - {message}{reset_code}")
            print(f"           Entry: {entry}, Full: {full}")
            
            # Get debug info for active cabin every 10 seconds
            if int(time.time()) % 10 == 0:
                debug = get_debug_cabin(active_cabin)
                if debug:
                    prev = debug.get("previous_state", {})
                    print(f"           Previous: entry={prev.get('entry')}, full={prev.get('full')}")
            
            time.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\nStopped monitoring")

if __name__ == "__main__":
    main()
