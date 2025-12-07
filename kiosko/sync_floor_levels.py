#!/usr/bin/env python3
"""
Sync floor levels from database to all cabin firmware via MQTT.

This script:
1. Reads floor levels from the database (cabinas.minimum_distance)
2. Sends set_floor_level MQTT command to each cabin's firmware
3. Reports which cabins were updated successfully

Usage:
    python sync_floor_levels.py

Environment variables (same as kiosko):
    MQTT_BROKER or KIOSKO_MQTT_HOST: MQTT broker host (default: 127.0.0.1)
    MQTT_PORT or KIOSKO_MQTT_PORT: MQTT broker port (default: 1883)
    MQTT_USER or KIOSKO_MQTT_USER: MQTT username (optional)
    MQTT_PASSWORD or KIOSKO_MQTT_PASSWORD: MQTT password (optional)
    MQTT_SITE: Site ID (default: garage-01)
    MQTT_TOPIC_BASE: Topic base (default: parking)
"""
import os
import sys
import json
import time
import sqlite3
from pathlib import Path
import paho.mqtt.client as mqtt

# Database path
DB_PATH = Path(__file__).resolve().parent / "kiosko.db"

def get_mqtt_config():
    """Get MQTT configuration from environment variables."""
    broker = os.getenv("KIOSKO_MQTT_HOST", os.getenv("MQTT_BROKER", "127.0.0.1"))
    port = int(os.getenv("KIOSKO_MQTT_PORT", os.getenv("MQTT_PORT", "1883")))
    username = os.getenv("KIOSKO_MQTT_USER", os.getenv("MQTT_USER"))
    password = os.getenv("KIOSKO_MQTT_PASSWORD", os.getenv("MQTT_PASSWORD"))
    site = os.getenv("MQTT_SITE", "garage-01")
    topic_base = os.getenv("MQTT_TOPIC_BASE", "parking")
    
    return {
        "broker": broker,
        "port": port,
        "username": username,
        "password": password,
        "site": site,
        "topic_base": topic_base
    }

def get_cabin_floor_levels():
    """Get floor levels for all cabins from database."""
    if not DB_PATH.exists():
        print(f"ERROR: Database file not found at {DB_PATH}")
        return {}
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cabins = cur.execute(
        "SELECT id, minimum_distance FROM cabinas ORDER BY id"
    ).fetchall()
    
    floor_levels = {}
    for cabin in cabins:
        cabin_id = cabin["id"]  # e.g., "CABINA-01"
        min_dist = cabin["minimum_distance"]
        
        if min_dist is not None and min_dist > 0:
            # Convert to MQTT format: CABINA-01 -> cabina-01
            cabin_id_mqtt = cabin_id.replace("CABINA-", "cabina-").lower()
            floor_levels[cabin_id_mqtt] = {
                "db_id": cabin_id,
                "floor_level_mm": min_dist
            }
    
    conn.close()
    return floor_levels

def send_floor_level_command(cabin_id_mqtt: str, floor_level_mm: int, mqtt_config: dict) -> bool:
    """Send set_floor_level MQTT command to a cabin.
    
    Returns:
        True if command was sent successfully, False otherwise
    """
    topic_base = mqtt_config["topic_base"]
    site = mqtt_config["site"]
    broker = mqtt_config["broker"]
    port = mqtt_config["port"]
    username = mqtt_config.get("username")
    password = mqtt_config.get("password")
    
    command_topic = f"{topic_base}/{site}/{cabin_id_mqtt}/cmd"
    command_payload = json.dumps({"set_floor_level": floor_level_mm})
    
    success = False
    error_msg = None
    
    def on_connect(client, userdata, flags, rc):
        nonlocal success
        if rc == 0:
            client.publish(command_topic, command_payload, qos=1, retain=False)
            # Give it a moment to send
            time.sleep(0.1)
            client.disconnect()
            success = True
        else:
            nonlocal error_msg
            error_msg = f"MQTT connection failed with rc={rc}"
    
    def on_publish(client, userdata, mid):
        pass  # Message published
    
    try:
        client_id = f"sync-floor-{cabin_id_mqtt}-{int(time.time())}"
        client = mqtt.Client(client_id=client_id)
        
        if username and password:
            client.username_pw_set(username, password)
        
        client.on_connect = on_connect
        client.on_publish = on_publish
        
        client.connect(broker, port, keepalive=60)
        client.loop_start()
        
        # Wait up to 5 seconds for connection and publish
        timeout = 5
        elapsed = 0
        while not success and elapsed < timeout:
            time.sleep(0.1)
            elapsed += 0.1
            if error_msg:
                break
        
        client.loop_stop()
        
        if error_msg:
            print(f"  ERROR: {error_msg}")
            return False
        
        if not success:
            print(f"  ERROR: Timeout sending command")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ERROR: Exception: {e}")
        return False

def main():
    """Main sync function."""
    print("=" * 60)
    print("Floor Level Sync Script")
    print("=" * 60)
    print()
    
    # Get MQTT configuration
    mqtt_config = get_mqtt_config()
    print(f"MQTT Broker: {mqtt_config['broker']}:{mqtt_config['port']}")
    print(f"Site: {mqtt_config['site']}")
    print(f"Topic Base: {mqtt_config['topic_base']}")
    print()
    
    # Get floor levels from database
    print("Reading floor levels from database...")
    floor_levels = get_cabin_floor_levels()
    
    if not floor_levels:
        print("WARNING: No cabins found with floor levels configured in database!")
        print("Use the API endpoint to set floor levels first:")
        print("  curl -X POST http://localhost:5000/api/cabin/CABINA-01/floor-level -H 'Content-Type: application/json' -d '{\"floor_level_mm\": 450}'")
        return 1
    
    print(f"Found {len(floor_levels)} cabin(s) with floor levels:")
    for cabin_id, info in sorted(floor_levels.items()):
        print(f"  {cabin_id}: {info['floor_level_mm']} mm")
    print()
    
    # Send commands to each cabin
    print("Sending set_floor_level commands to firmware...")
    print()
    
    results = {}
    for cabin_id_mqtt, info in sorted(floor_levels.items()):
        floor_level_mm = info["floor_level_mm"]
        db_id = info["db_id"]
        
        print(f"Sending to {cabin_id_mqtt} ({db_id}): {floor_level_mm} mm...", end=" ", flush=True)
        
        success = send_floor_level_command(cabin_id_mqtt, floor_level_mm, mqtt_config)
        results[cabin_id_mqtt] = success
        
        if success:
            print("✓ OK")
        else:
            print("✗ FAILED")
    
    print()
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    
    success_count = sum(1 for s in results.values() if s)
    failed_count = len(results) - success_count
    
    print(f"Successful: {success_count}/{len(results)}")
    print(f"Failed: {failed_count}/{len(results)}")
    print()
    
    if failed_count > 0:
        print("Failed cabins:")
        for cabin_id, success in sorted(results.items()):
            if not success:
                print(f"  - {cabin_id}")
        print()
        print("Note: The firmware needs to be online and connected to MQTT to receive commands.")
        print("      The floor level will be saved to NVS on the next boot if the command was received.")
        return 1
    
    print("✓ All cabins updated successfully!")
    print()
    print("Note: Each cabin will save the floor level to NVS and start detecting floor/reached events.")
    print("      Check the cabin's serial output to verify 'Floor level set via MQTT command' log.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())