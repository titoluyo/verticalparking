#!/usr/bin/env python3
"""Quick status check script."""
import requests
import json
import sys

SERVER = "192.168.10.50"
PORT = 5000
BASE_URL = f"http://{SERVER}:{PORT}/api"

try:
    # Get active cabin
    r = requests.get(f"{BASE_URL}/active-cabin", timeout=5)
    active = r.json()
    print(f"Active cabin: {active.get('active_cabin')}")
    
    # Get presence
    r = requests.get(f"{BASE_URL}/presence", timeout=5)
    presence = r.json()
    print(f"State: {presence.get('state')} - {presence.get('message')}")
    print(f"Entry: {presence.get('entry', {}).get('present')}, Full: {presence.get('full', {}).get('present')}")
    
    # Get debug for active cabin
    active_cabin = active.get('active_cabin')
    if active_cabin:
        r = requests.get(f"{BASE_URL}/presence/debug/cabin/{active_cabin}", timeout=5)
        debug = r.json()
        prev = debug.get('previous_state', {})
        print(f"Previous: entry={prev.get('entry')}, full={prev.get('full')}")
        print(f"Computed: {debug.get('computed_state', {}).get('state')} - {debug.get('computed_state', {}).get('message')}")
    
    sys.exit(0)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
