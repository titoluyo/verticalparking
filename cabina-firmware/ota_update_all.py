#!/usr/bin/env python3
"""
OTA update script for multiple ESP32 cabins via MQTT.

This script sends OTA update commands to multiple devices simultaneously.
Each device will download and install the firmware from the specified URL.

Usage:
    python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin
    python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin --device-id cabina-01
    python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin --site-id garage-01
"""

import argparse
import json
import paho.mqtt.client as mqtt
import sys
import time
from typing import List, Optional

# Default configuration
DEFAULT_MQTT_BROKER = "192.168.10.50"
DEFAULT_MQTT_PORT = 1883
DEFAULT_TOPIC_BASE = "parking"
DEFAULT_SITE_ID = "garage-01"

# Default device IDs (edit as needed)
DEFAULT_DEVICE_IDS = [
    "cabina-00",
    "cabina-01",
    "cabina-02",
    "cabina-03",
    "cabina-04",
    "cabina-05",
    "cabina-06",
    # Add more as needed
]


class OTAUpdater:
    def __init__(self, broker: str, port: int, topic_base: str, site_id: str):
        self.broker = broker
        self.port = port
        self.topic_base = topic_base
        self.site_id = site_id
        self.client = None
        self.results = {}
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✓ Connected to MQTT broker {self.broker}:{self.port}")
        else:
            print(f"✗ Failed to connect to MQTT broker, return code {rc}", file=sys.stderr)
            
    def on_message(self, client, userdata, msg):
        """Handle OTA status messages from devices."""
        topic = msg.topic
        try:
            data = json.loads(msg.payload.decode())
            device_id = data.get("device", "unknown")
            status = data.get("ota_status", "unknown")
            progress = data.get("progress", 0)
            message = data.get("message", "")
            
            # Store status for this device
            if device_id not in self.results:
                self.results[device_id] = {"status": "unknown", "progress": 0, "message": ""}
            
            self.results[device_id]["status"] = status
            self.results[device_id]["progress"] = progress
            self.results[device_id]["message"] = message
            
            # Print status update
            if status in ["downloading", "verifying", "applying"]:
                print(f"  [{device_id}] {status}: {progress}% - {message}")
            elif status == "success":
                print(f"  ✓ [{device_id}] Update successful!")
            elif status == "failed":
                print(f"  ✗ [{device_id}] Update failed: {message}")
                
        except Exception as e:
            print(f"  ⚠ Error parsing message from {topic}: {e}", file=sys.stderr)
    
    def connect(self):
        """Connect to MQTT broker."""
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            time.sleep(1)  # Wait for connection
            return True
        except Exception as e:
            print(f"✗ Failed to connect to MQTT broker: {e}", file=sys.stderr)
            return False
    
    def subscribe_to_status(self, device_ids: List[str]):
        """Subscribe to OTA status topics for all devices."""
        for device_id in device_ids:
            topic = f"{self.topic_base}/{self.site_id}/{device_id}/ota/status"
            self.client.subscribe(topic, qos=1)
            print(f"  Subscribed to: {topic}")
    
    def send_ota_command(self, device_id: str, firmware_url: str, force: bool = False):
        """Send OTA update command to a specific device."""
        topic = f"{self.topic_base}/{self.site_id}/{device_id}/ota/update"
        payload = json.dumps({"url": firmware_url, "force": force})
        
        result = self.client.publish(topic, payload, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"  ✓ Sent OTA command to {device_id} -> {firmware_url}")
            return True
        else:
            print(f"  ✗ Failed to send OTA command to {device_id}", file=sys.stderr)
            return False
    
    def update_devices(self, device_ids: List[str], firmware_url: str, force: bool = False, timeout: int = 300, url_map: Optional[dict] = None):
        """Send OTA update commands to multiple devices and monitor progress."""
        print(f"\n{'='*60}")
        print(f"OTA Update for {len(device_ids)} devices")
        print(f"{'='*60}")
        if url_map:
            print(f"Using URL mapping for device-specific firmware")
            for dev_id, url in url_map.items():
                if dev_id in device_ids:
                    print(f"  {dev_id}: {url}")
        else:
            print(f"Firmware URL: {firmware_url}")
        print(f"Devices: {', '.join(device_ids)}")
        print(f"{'='*60}\n")
        
        # Subscribe to status topics
        print("Subscribing to OTA status topics...")
        self.subscribe_to_status(device_ids)
        time.sleep(1)
        
        # Send OTA commands
        print(f"\nSending OTA update commands...")
        success_count = 0
        for device_id in device_ids:
            # Use device-specific URL if provided, otherwise use default
            if url_map:
                url = url_map.get(device_id)
                if not url:
                    print(f"  ⚠ No URL mapping for {device_id}, skipping", file=sys.stderr)
                    continue
            else:
                url = firmware_url
            if self.send_ota_command(device_id, url, force):
                success_count += 1
            time.sleep(0.5)  # Small delay between commands
        
        print(f"\n✓ Sent commands to {success_count}/{len(device_ids)} devices")
        
        # Monitor progress
        print(f"\nMonitoring updates (timeout: {timeout}s)...")
        print("Press Ctrl+C to stop monitoring (updates will continue on devices)\n")
        
        start_time = time.time()
        completed = set()
        
        try:
            while len(completed) < len(device_ids) and (time.time() - start_time) < timeout:
                time.sleep(2)
                
                for device_id in device_ids:
                    if device_id in completed:
                        continue
                        
                    result = self.results.get(device_id, {})
                    status = result.get("status", "")
                    
                    if status == "success":
                        completed.add(device_id)
                    elif status == "failed":
                        completed.add(device_id)
                        
            # Print final summary
            print(f"\n{'='*60}")
            print(f"OTA Update Summary")
            print(f"{'='*60}")
            
            for device_id in device_ids:
                result = self.results.get(device_id, {})
                status = result.get("status", "unknown")
                message = result.get("message", "")
                
                if status == "success":
                    print(f"  ✓ {device_id}: Success")
                elif status == "failed":
                    print(f"  ✗ {device_id}: Failed - {message}")
                else:
                    print(f"  ? {device_id}: Status unknown (may still be updating)")
            
            print(f"{'='*60}\n")
            
        except KeyboardInterrupt:
            print(f"\n\nMonitoring stopped by user. Updates may still be in progress on devices.")
            print(f"Check device logs or MQTT status topics for final results.")
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description="OTA update multiple ESP32 cabins via MQTT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update all default devices (same firmware)
  python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin
  
  # Update specific device
  python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin --device-id cabina-01
  
  # Update multiple specific devices
  python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin --device-id cabina-01 --device-id cabina-02
  
  # Update all devices in a different site
  python ota_update_all.py --firmware-url http://192.168.10.147:8080/cabina-firmware.bin --site-id garage-02
  
  # Update with different firmware per device (using URL mapping)
  python ota_update_all.py --url-map url_map.json
        """
    )
    
    parser.add_argument(
        '--firmware-url',
        help='HTTP/HTTPS URL to firmware binary (default URL for all devices)'
    )
    
    parser.add_argument(
        '--url-map',
        help='JSON file mapping device IDs to firmware URLs. Format: {"cabina-01": "http://...", "cabina-02": "http://..."}'
    )
    
    parser.add_argument(
        '--device-id',
        action='append',
        dest='device_ids',
        help='Device ID to update (can be specified multiple times). If not specified, updates all default devices.'
    )
    
    parser.add_argument(
        '--site-id',
        default=DEFAULT_SITE_ID,
        help=f'Site ID (default: {DEFAULT_SITE_ID})'
    )
    
    parser.add_argument(
        '--topic-base',
        default=DEFAULT_TOPIC_BASE,
        help=f'MQTT topic base (default: {DEFAULT_TOPIC_BASE})'
    )
    
    parser.add_argument(
        '--broker',
        default=DEFAULT_MQTT_BROKER,
        help=f'MQTT broker address (default: {DEFAULT_MQTT_BROKER})'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_MQTT_PORT,
        help=f'MQTT broker port (default: {DEFAULT_MQTT_PORT})'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force update even if one is already in progress'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Timeout in seconds for monitoring updates (default: 300)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.firmware_url and not args.url_map:
        print("ERROR: Must specify either --firmware-url or --url-map", file=sys.stderr)
        sys.exit(1)
    
    # Load URL mapping if provided
    url_map = None
    if args.url_map:
        try:
            with open(args.url_map, 'r') as f:
                url_map = json.load(f)
            print(f"Loaded URL mapping from {args.url_map}")
            # If URL map provided, use its device IDs
            if not args.device_ids:
                device_ids = list(url_map.keys())
            else:
                device_ids = args.device_ids
        except Exception as e:
            print(f"ERROR: Failed to load URL map: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Determine device IDs to update
        if args.device_ids:
            device_ids = args.device_ids
        else:
            device_ids = DEFAULT_DEVICE_IDS
    
    # Default firmware URL (used if not in url_map)
    firmware_url = args.firmware_url or ""
    
    # Create updater and connect
    updater = OTAUpdater(args.broker, args.port, args.topic_base, args.site_id)
    
    if not updater.connect():
        sys.exit(1)
    
    try:
        # Send updates
        updater.update_devices(device_ids, firmware_url, args.force, args.timeout, url_map)
    finally:
        updater.disconnect()


if __name__ == '__main__':
    main()

