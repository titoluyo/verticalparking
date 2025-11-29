"""Lightweight JSON API for kiosk front-end widgets."""
import json
import os
import queue
import threading
import time

import paho.mqtt.client as mqtt
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context


bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/presence", methods=["GET"])
def presence_status():
    service = current_app.config.get("PRESENCE_SERVICE")
    if not service:
        return jsonify({"error": "presence service unavailable"}), 503
    return jsonify(service.snapshot())


@bp.route("/presence/stream", methods=["GET"])
def presence_stream():
    """Server-Sent Events stream for real-time presence updates."""
    service = current_app.config.get("PRESENCE_SERVICE")
    if not service:
        return jsonify({"error": "presence service unavailable"}), 503
    
    def generate():
        # Subscribe to presence updates
        client_queue = service.subscribe()
        
        try:
            # Send initial state immediately
            snapshot = service.snapshot()
            yield f"data: {json.dumps(snapshot)}\n\n"
            
            # Keepalive timer
            last_keepalive = time.time()
            keepalive_interval = 30  # seconds
            
            while True:
                try:
                    # Wait for updates with timeout for keepalive
                    timeout = max(1.0, keepalive_interval - (time.time() - last_keepalive))
                    try:
                        snapshot_json = client_queue.get(timeout=timeout)
                        yield f"data: {snapshot_json}\n\n"
                    except queue.Empty:
                        # Timeout - send keepalive
                        current_time = time.time()
                        if current_time - last_keepalive >= keepalive_interval:
                            yield ": keepalive\n\n"
                            last_keepalive = current_time
                except GeneratorExit:
                    # Client disconnected
                    break
                except Exception as e:
                    current_app.logger.error("Error in SSE stream: %s", e)
                    break
        finally:
            # Clean up subscription
            service.unsubscribe(client_queue)
    
    response = Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
            "Connection": "keep-alive",
        },
    )
    return response


@bp.route("/sensors/cabins", methods=["GET"])
def check_cabin_sensors():
    """Check sensor status for multiple cabins (cabin-01 to cabin-07)."""
    # Get cabin range from query params or default to cabin-01 to cabin-07
    start_cabin = request.args.get("start", "cabin-01")
    end_cabin = request.args.get("end", "cabin-07")
    
    # Parse cabin numbers
    try:
        if start_cabin.startswith("cabin-") and end_cabin.startswith("cabin-"):
            start_num = int(start_cabin[6:])
            end_num = int(end_cabin[6:])
            cabins = [f"cabin-{i:02d}" for i in range(start_num, end_num + 1)]
        else:
            return jsonify({"error": "Invalid cabin format. Use cabin-01-cabin-07 format"}), 400
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid cabin format. Use cabin-01-cabin-07 format"}), 400
    
    # Get MQTT configuration from environment
    broker = os.getenv("KIOSKO_MQTT_HOST", os.getenv("MQTT_BROKER", "127.0.0.1"))
    port = int(os.getenv("KIOSKO_MQTT_PORT", os.getenv("MQTT_PORT", "1883")))
    username = os.getenv("KIOSKO_MQTT_USER", os.getenv("MQTT_USER"))
    password = os.getenv("KIOSKO_MQTT_PASSWORD", os.getenv("MQTT_PASSWORD"))
    topic_base = os.getenv("KIOSKO_TOPIC_BASE", os.getenv("TOPIC_BASE", "parking"))
    site = os.getenv("KIOSKO_SITE_ID", os.getenv("SITE_ID", "garage-01"))
    
    # Results storage
    results = {}
    messages_received = {}
    lock = threading.Lock()
    connection_event = threading.Event()
    timeout_event = threading.Event()
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            connection_event.set()
            # Subscribe to all presence topics for the cabins
            for cabin in cabins:
                # Cabin ID already includes "cabin-" prefix, use it directly
                device_id = cabin
                topic_entry = f"{topic_base}/{site}/{device_id}/presence/entry"
                topic_full = f"{topic_base}/{site}/{device_id}/presence/full"
                client.subscribe(topic_entry, qos=1)
                client.subscribe(topic_full, qos=1)
                current_app.logger.debug("Subscribed to %s and %s", topic_entry, topic_full)
        else:
            current_app.logger.error("MQTT connection failed with rc=%s", rc)
    
    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            device = payload.get("device", "")
            sensor = payload.get("sensor", "")
            present = bool(payload.get("present", False))
            ts = payload.get("ts")
            
            # Extract cabin from device name (e.g., "cabin-01" -> "cabin-01")
            if device.startswith("cabin-"):
                cabin = device  # Cabin ID already includes "cabin-" prefix
            else:
                # Try to extract from topic
                parts = msg.topic.split("/")
                if len(parts) >= 3:
                    device_part = parts[2]
                    if device_part.startswith("cabin-"):
                        cabin = device_part
                    else:
                        return
                else:
                    return
            
            if cabin not in cabins:
                return
            
            with lock:
                if cabin not in results:
                    results[cabin] = {
                        "entry": {"present": False, "ts": None},
                        "full": {"present": False, "ts": None},
                    }
                
                # Update sensor state
                if sensor == "ir1" or "entry" in msg.topic:
                    results[cabin]["entry"] = {"present": present, "ts": ts}
                    messages_received[f"{cabin}/entry"] = True
                elif sensor == "ir2" or "full" in msg.topic:
                    results[cabin]["full"] = {"present": present, "ts": ts}
                    messages_received[f"{cabin}/full"] = True
                
                # Check if we've received all expected messages
                expected_count = len(cabins) * 2  # 2 sensors per cabin
                if len(messages_received) >= expected_count:
                    timeout_event.set()
        except Exception as e:
            current_app.logger.warning("Error processing MQTT message: %s", e)
    
    def on_subscribe(client, userdata, mid, granted_qos):
        current_app.logger.debug("Subscribed with mid=%s, qos=%s", mid, granted_qos)
    
    # Create MQTT client
    client = mqtt.Client(client_id=f"kiosko-sensor-check-{int(time.time())}", clean_session=True)
    if username:
        client.username_pw_set(username, password)
    
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_subscribe = on_subscribe
    
    try:
        # Connect to broker
        current_app.logger.info("Connecting to MQTT broker %s:%s to check cabin sensors", broker, port)
        client.connect(broker, port, keepalive=30)
        client.loop_start()
        
        # Wait for connection (max 5 seconds)
        if not connection_event.wait(timeout=5):
            client.loop_stop()
            client.disconnect()
            return jsonify({"error": "Failed to connect to MQTT broker"}), 503
        
        # Wait for messages (max 3 seconds)
        timeout_event.wait(timeout=3)
        
        # Give a bit more time for retained messages
        time.sleep(0.5)
        
        client.loop_stop()
        client.disconnect()
        
        # Format response
        response_data = {
            "cabins": {},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        
        for cabin in cabins:
            if cabin in results:
                entry = results[cabin]["entry"]
                full = results[cabin]["full"]
                entry_present = entry["present"]
                full_present = full["present"]
                
                # Determine state
                if full_present:
                    state = "occupied"
                    message = "Vehículo detectado"
                elif entry_present:
                    state = "transitioning"
                    message = "Vehículo ingresando..."
                else:
                    state = "free"
                    message = "Espacio libre"
                
                response_data["cabins"][cabin] = {
                    "entry": {
                        "present": entry_present,
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry["ts"])) if entry["ts"] else None,
                    },
                    "full": {
                        "present": full_present,
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(full["ts"])) if full["ts"] else None,
                    },
                    "state": state,
                    "message": message,
                    "occupied": full_present,
                }
            else:
                # No data received for this cabin
                response_data["cabins"][cabin] = {
                    "entry": {"present": False, "ts": None},
                    "full": {"present": False, "ts": None},
                    "state": "unknown",
                    "message": "Sin datos del sensor",
                    "occupied": False,
                }
        
        return jsonify(response_data)
        
    except Exception as e:
        current_app.logger.exception("Error checking cabin sensors: %s", e)
        try:
            client.loop_stop()
            client.disconnect()
        except:
            pass
        return jsonify({"error": f"Failed to check sensors: {str(e)}"}), 500
