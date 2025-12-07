"""Lightweight JSON API for kiosk front-end widgets."""
import json
import logging
import os
import queue
import threading
import time
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import paho.mqtt.client as mqtt
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from .database import cleanup_tickets, reset_cabins, cleanup_all, get_ticket_by_token, get_all_cabins, update_cabin_minimum_distance, get_cabin
from .motor_control import MotorControlService
from .qr_detector import QRDetector


bp = Blueprint("api", __name__, url_prefix="/api")

# Module-level logger for MQTT callbacks (they run in separate threads)
logger = logging.getLogger(__name__)

# Distance cache: stores last known distance and minimum distance for each cabin
# Format: {"cabina-01": {"mm": 542, "min_mm": 500, "ts": 1234567890.123}, ...}
_distance_cache = {}
_distance_cache_lock = threading.Lock()


@bp.route("/presence", methods=["GET"])
def presence_status():
    """Get presence status for the active cabin (or all cabins if specified)."""
    service = current_app.config.get("PRESENCE_SERVICE")
    if not service:
        return jsonify({"error": "presence service unavailable"}), 503
    # In multi-cabin mode, snapshot() automatically returns active cabin's data
    return jsonify(service.snapshot())


@bp.route("/active-cabin", methods=["GET"])
def get_active_cabin():
    """Get the current active cabin ID."""
    service = current_app.config.get("PRESENCE_SERVICE")
    if not service:
        return jsonify({"error": "presence service unavailable"}), 503
    
    active_cabin = service.get_active_cabin()
    return jsonify({"active_cabin": active_cabin})


@bp.route("/active-cabin", methods=["POST"])
def set_active_cabin():
    """Set the active cabin for vehicle entrance monitoring."""
    service = current_app.config.get("PRESENCE_SERVICE")
    if not service:
        return jsonify({"error": "presence service unavailable"}), 503
    
    data = request.get_json()
    if not data or "cabin_id" not in data:
        return jsonify({"error": "Missing cabin_id in request body"}), 400
    
    cabin_id = data.get("cabin_id")
    if not isinstance(cabin_id, str):
        return jsonify({"error": "cabin_id must be a string"}), 400
    
    success = service.set_active_cabin(cabin_id)
    if success:
        return jsonify({"active_cabin": cabin_id, "message": "Active cabin updated"}), 200
    else:
        return jsonify({"error": f"Invalid cabin_id: {cabin_id}"}), 400


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
    """Check sensor status for multiple cabins (cabina-01 to cabina-06)."""
    # Get cabin range from query params or default to cabina-01 to cabina-06
    start_cabin = request.args.get("start", "cabina-01")
    end_cabin = request.args.get("end", "cabina-06")
    
    # Parse cabin numbers
    try:
        if start_cabin.startswith("cabina-") and end_cabin.startswith("cabina-"):
            start_num = int(start_cabin[7:])
            end_num = int(end_cabin[7:])
            cabins = [f"cabina-{i:02d}" for i in range(start_num, end_num + 1)]
        else:
            return jsonify({"error": "Invalid cabin format. Use cabina-01-cabina-06 format"}), 400
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid cabin format. Use cabina-01-cabina-06 format"}), 400
    
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
                # Cabin ID already includes "cabina-" prefix, use it directly
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
            
            # Extract cabin from device name (e.g., "cabina-01" -> "cabina-01")
            if device.startswith("cabina-"):
                cabin = device  # Cabin ID already includes "cabina-" prefix
            else:
                # Try to extract from topic
                parts = msg.topic.split("/")
                if len(parts) >= 3:
                    device_part = parts[2]
                    if device_part.startswith("cabina-"):
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


@bp.route("/printer/status", methods=["GET"])
def printer_status():
    """Get printer status information."""
    service = current_app.config.get("PRINTER_SERVICE")
    if not service:
        return jsonify({"error": "printer service unavailable"}), 503
    
    status = service.get_status()
    return jsonify(status)


@bp.route("/printer/test", methods=["POST"])
def printer_test():
    """Print a test ticket."""
    service = current_app.config.get("PRINTER_SERVICE")
    if not service:
        return jsonify({"error": "printer service unavailable"}), 503
    
    success = service.print_test()
    if success:
        return jsonify({"success": True, "message": "Test ticket printed successfully"}), 200
    else:
        status = service.get_status()
        return jsonify({
            "success": False,
            "error": "Failed to print test ticket",
            "status": status
        }), 503


@bp.route("/printer/entry-ticket", methods=["POST"])
def print_entry_ticket():
    """Print an entry ticket for a vehicle."""
    service = current_app.config.get("PRINTER_SERVICE")
    if not service:
        return jsonify({"error": "printer service unavailable"}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    
    vehicle_plate = data.get("vehicle_plate", "")  # Optional, not displayed on ticket
    cabin_id = data.get("cabin_id")
    timestamp = data.get("timestamp")
    ticket_id = data.get("ticket_id")
    
    if not cabin_id:
        return jsonify({"error": "Missing required field: cabin_id"}), 400
    
    success = service.print_entry_ticket(
        vehicle_plate=vehicle_plate,
        cabin_id=cabin_id,
        timestamp=timestamp,
        ticket_id=ticket_id
    )
    
    if success:
        return jsonify({
            "success": True,
            "message": "Entry ticket printed successfully",
            "cabin_id": cabin_id,
            "ticket_id": ticket_id
        }), 200
    else:
        status = service.get_status()
        return jsonify({
            "success": False,
            "error": "Failed to print entry ticket",
            "status": status
        }), 503


@bp.route("/printer/exit-ticket", methods=["POST"])
def print_exit_ticket():
    """Print an exit ticket for a vehicle."""
    service = current_app.config.get("PRINTER_SERVICE")
    if not service:
        return jsonify({"error": "printer service unavailable"}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    
    vehicle_plate = data.get("vehicle_plate")
    entry_time = data.get("entry_time")
    exit_time = data.get("exit_time")
    duration = data.get("duration")
    cost = data.get("cost")
    
    if not vehicle_plate:
        return jsonify({"error": "Missing required field: vehicle_plate"}), 400
    if not entry_time:
        return jsonify({"error": "Missing required field: entry_time"}), 400
    if not exit_time:
        return jsonify({"error": "Missing required field: exit_time"}), 400
    if duration is None:
        return jsonify({"error": "Missing required field: duration"}), 400
    if cost is None:
        return jsonify({"error": "Missing required field: cost"}), 400
    
    success = service.print_exit_ticket(
        vehicle_plate=vehicle_plate,
        entry_time=entry_time,
        exit_time=exit_time,
        duration=str(duration),
        cost=str(cost)
    )
    
    if success:
        return jsonify({
            "success": True,
            "message": "Exit ticket printed successfully",
            "vehicle_plate": vehicle_plate
        }), 200
    else:
        status = service.get_status()
        return jsonify({
            "success": False,
            "error": "Failed to print exit ticket",
            "status": status
        }), 503


@bp.route("/camera/status", methods=["GET"])
def camera_status():
    """Get camera service status information."""
    video_service = current_app.config.get("VIDEO_STREAM_SERVICE")
    current_app.logger.info(f"VideoStreamService in config: {video_service is not None}")
    
    if video_service:
        video_status = video_service.get_status()
        current_app.logger.info(f"VideoStreamService status: {video_status}")
        available = video_status.get("available", False)
    else:
        video_status = None
        available = False
        current_app.logger.warning("VideoStreamService not found in config")
    
    response = {
        "video_stream": video_status,
        "available": available,
        "enabled": video_status.get("enabled", False) if video_status else False
    }
    
    # Include error message if available
    if video_status and "error" in video_status:
        response["error"] = video_status["error"]
    
    return jsonify(response)


@bp.route("/camera/stream", methods=["GET"])
def camera_stream():
    """MJPEG video stream from camera using picamera2 hardware encoder.
    
    Based on the picamera2 MJPEG server example.
    """
    video_service = current_app.config.get("VIDEO_STREAM_SERVICE")
    if not video_service:
        current_app.logger.error("VideoStreamService not configured")
        return _generate_error_frame("Servicio de video no configurado"), 503
    
    if not video_service.is_available():
        current_app.logger.error("VideoStreamService not available")
        status = video_service.get_status()
        return _generate_error_frame(f"Video stream no disponible (available: {status.get('available', False)})"), 503
    
    output = video_service.get_output()
    if not output:
        current_app.logger.error("VideoStreamService output not available")
        return _generate_error_frame("Salida de video no disponible"), 503
    
    def generate():
        """Generate MJPEG frames from picamera2 hardware encoder."""
        try:
            while True:
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                if frame:
                    yield (b'--FRAME\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(frame)).encode() + b'\r\n'
                           b'\r\n')
                    yield frame
                    yield b'\r\n'
        except Exception as e:
            current_app.logger.warning(f"Camera stream client disconnected: {e}")
    
    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=FRAME'
    )


def _generate_error_frame(message: str):
    """Generate a simple error frame as JPEG using PIL."""
    if not PIL_AVAILABLE:
        # Return a simple text response if PIL is not available
        return Response(
            f"Error: {message}",
            mimetype='text/plain',
            status=503
        )
    
    # Create a simple error image
    try:
        img = Image.new('RGB', (640, 480), color=(50, 50, 50))  # Dark gray background
        draw = ImageDraw.Draw(img)
        
        # Try to use a nice font, fallback to default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 24)
            except:
                font = ImageFont.load_default()
        
        # Calculate text position (centered)
        bbox = draw.textbbox((0, 0), message, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (640 - text_width) // 2
        text_y = (480 - text_height) // 2
        
        # Draw text
        draw.text((text_x, text_y), message, fill=(255, 255, 255), font=font)
        
        # Encode as JPEG
        import io
        jpeg_buffer = io.BytesIO()
        img.save(jpeg_buffer, format='JPEG', quality=85)
        jpeg_bytes = jpeg_buffer.getvalue()
        
        return Response(
            b'--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(jpeg_bytes)).encode() + b'\r\n\r\n' + jpeg_bytes + b'\r\n',
            mimetype='multipart/x-mixed-replace; boundary=FRAME'
        )
    except Exception as e:
        return Response(f"Error generating frame: {e}", status=503)


def _generate_error_frame_bytes(message: str) -> bytes:
    """Generate error frame bytes for streaming using PIL."""
    if not PIL_AVAILABLE:
        return b'--FRAME\r\nContent-Type: text/plain\r\n\r\nError: ' + message.encode() + b'\r\n'
    
    try:
        img = Image.new('RGB', (640, 480), color=(50, 50, 50))  # Dark gray background
        draw = ImageDraw.Draw(img)
        
        # Try to use a nice font, fallback to default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 24)
            except:
                font = ImageFont.load_default()
        
        # Calculate text position (centered)
        bbox = draw.textbbox((0, 0), message, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (640 - text_width) // 2
        text_y = (480 - text_height) // 2
        
        # Draw text
        draw.text((text_x, text_y), message, fill=(255, 255, 255), font=font)
        
        # Encode as JPEG
        import io
        jpeg_buffer = io.BytesIO()
        img.save(jpeg_buffer, format='JPEG', quality=85)
        jpeg_bytes = jpeg_buffer.getvalue()
        
        return b'--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(jpeg_bytes)).encode() + b'\r\n\r\n' + jpeg_bytes + b'\r\n'
    except Exception as e:
        return b'--FRAME\r\nContent-Type: text/plain\r\n\r\nError: ' + str(e).encode() + b'\r\n'


@bp.route("/camera/detect", methods=["POST"])
def camera_detect_qr():
    """Detect QR codes from an uploaded image frame.
    
    Request: multipart/form-data with 'frame' file (JPEG/PNG)
    
    Returns:
        JSON with detected QR codes
    """
    current_app.logger.debug("QR detection request received")
    
    if 'frame' not in request.files:
        current_app.logger.warning("QR detection request missing 'frame' file")
        return jsonify({"error": "Missing 'frame' file in request"}), 400
    
    file = request.files['frame']
    if file.filename == '':
        current_app.logger.warning("QR detection request with empty filename")
        return jsonify({"error": "No file selected"}), 400
    
    # Get QR detector from app config
    qr_detector = current_app.config.get("QR_DETECTOR")
    if not qr_detector or not qr_detector.is_available():
        current_app.logger.warning("QR detection requested but detector not available")
        return jsonify({"error": "QR detection not available"}), 503
    
    try:
        # Read image bytes
        image_bytes = file.read()
        current_app.logger.debug(f"Processing QR detection for image: {len(image_bytes)} bytes")
        
        # Detect QR codes
        qr_codes = qr_detector.detect_from_bytes(image_bytes)
        
        if qr_codes:
            current_app.logger.info(f"QR detection successful: found {len(qr_codes)} QR code(s)")
        else:
            current_app.logger.debug("QR detection: no QR codes found in image")
        
        return jsonify({
            "success": True,
            "count": len(qr_codes),
            "qr_codes": qr_codes
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error detecting QR codes: {e}", exc_info=True)
        return jsonify({"error": f"Error processing image: {str(e)}"}), 500


@bp.route("/calibrate/cabin/<cabin_id>", methods=["POST"])
def calibrate_cabin(cabin_id: str):
    """Start calibration for a cabin.
    
    This endpoint:
    1. Sends start_calibration command to the cabin
    2. Starts the motor (sends "ON" to motor topic)
    3. Returns status immediately
    4. Calibration completion will be handled via MQTT event callbacks
    
    Args:
        cabin_id: Cabin ID (e.g., "cabina-01" or "CABINA-01")
    
    Returns:
        JSON with calibration status
    """
    # Normalize cabin ID format
    if cabin_id.startswith("CABINA-"):
        cabin_id_mqtt = cabin_id.replace("CABINA-", "cabina-").lower()
    elif cabin_id.startswith("cabina-"):
        cabin_id_mqtt = cabin_id.lower()
    else:
        # Try to parse as number
        try:
            num = int(cabin_id)
            cabin_id_mqtt = f"cabina-{num:02d}"
        except ValueError:
            return jsonify({"error": f"Invalid cabin_id format: {cabin_id}"}), 400
    
    # Get motor control service
    motor_service = current_app.config.get("MOTOR_CONTROL_SERVICE")
    if not motor_service:
        return jsonify({"error": "Motor control service unavailable"}), 503
    
    # Check if already calibrating
    if motor_service.is_calibrating(cabin_id_mqtt):
        return jsonify({
            "success": False,
            "error": f"Cabin {cabin_id_mqtt} is already calibrating",
            "cabin_id": cabin_id_mqtt
        }), 400
    
    # Send calibration start command
    success = motor_service.send_calibration_command(cabin_id_mqtt, "start")
    if not success:
        return jsonify({
            "success": False,
            "error": "Failed to send calibration command",
            "cabin_id": cabin_id_mqtt
        }), 500
    
    # Start motor (calibration requires motor to run)
    motor_started = motor_service.start_motor(cabin_id_mqtt)
    if not motor_started:
        current_app.logger.warning(f"Calibration started for {cabin_id_mqtt} but motor start failed")
    
    current_app.logger.info(f"Calibration started for {cabin_id_mqtt}")
    
    return jsonify({
        "success": True,
        "message": f"Calibration started for {cabin_id_mqtt}",
        "cabin_id": cabin_id_mqtt,
        "motor_started": motor_started,
        "expected_duration": "2 full rotations (time varies by motor speed)"
    }), 200


@bp.route("/calibrate/cabin/<cabin_id>/stop", methods=["POST"])
def stop_calibration(cabin_id: str):
    """Stop calibration for a cabin (emergency cancel).
    
    Args:
        cabin_id: Cabin ID (e.g., "cabina-01" or "CABINA-01")
    
    Returns:
        JSON with status
    """
    # Normalize cabin ID format
    if cabin_id.startswith("CABINA-"):
        cabin_id_mqtt = cabin_id.replace("CABINA-", "cabina-").lower()
    elif cabin_id.startswith("cabina-"):
        cabin_id_mqtt = cabin_id.lower()
    else:
        try:
            num = int(cabin_id)
            cabin_id_mqtt = f"cabina-{num:02d}"
        except ValueError:
            return jsonify({"error": f"Invalid cabin_id format: {cabin_id}"}), 400
    
    # Get motor control service
    motor_service = current_app.config.get("MOTOR_CONTROL_SERVICE")
    if not motor_service:
        return jsonify({"error": "Motor control service unavailable"}), 503
    
    # Send calibration stop command
    success = motor_service.send_calibration_command(cabin_id_mqtt, "stop")
    if not success:
        return jsonify({
            "success": False,
            "error": "Failed to send stop calibration command",
            "cabin_id": cabin_id_mqtt
        }), 500
    
    # Stop motor
    motor_service.stop_motor(cabin_id_mqtt)
    
    current_app.logger.info(f"Calibration stopped for {cabin_id_mqtt}")
    
    return jsonify({
        "success": True,
        "message": f"Calibration stopped for {cabin_id_mqtt}",
        "cabin_id": cabin_id_mqtt
    }), 200


@bp.route("/cabin/<cabin_id>/floor-level", methods=["POST"])
def set_floor_level(cabin_id: str):
    """Set the floor level (minimum distance) for a cabin manually.
    
    This is a simple endpoint to set the floor level without calibration.
    Use this when you know the floor level distance in mm.
    
    Request body (JSON):
    {
        "floor_level_mm": 450
    }
    
    Or via query parameter:
    ?floor_level_mm=450
    
    Example with curl:
    curl -X POST http://localhost:5000/api/cabin/cabina-01/floor-level -H "Content-Type: application/json" -d '{"floor_level_mm": 450}'
    curl -X POST "http://localhost:5000/api/cabin/CABINA-01/floor-level?floor_level_mm=450"
    
    Args:
        cabin_id: Cabin ID (e.g., "cabina-01", "CABINA-01", or "01")
    
    Returns:
        JSON with success status
    """
    # Normalize cabin ID format
    if cabin_id.startswith("CABINA-"):
        cabin_id_db = cabin_id
        cabin_id_mqtt = cabin_id.replace("CABINA-", "cabina-").lower()
    elif cabin_id.startswith("cabina-"):
        cabin_id_db = cabin_id.replace("cabina-", "CABINA-").upper()
        cabin_id_mqtt = cabin_id.lower()
    else:
        # Try to parse as number
        try:
            num = int(cabin_id)
            cabin_id_db = f"CABINA-{num:02d}"
            cabin_id_mqtt = f"cabina-{num:02d}"
        except ValueError:
            return jsonify({"error": f"Invalid cabin_id format: {cabin_id}"}), 400
    
    # Get floor level from request body or query parameter
    data = request.get_json() or {}
    floor_level_mm = data.get("floor_level_mm")
    
    if floor_level_mm is None:
        # Try query parameter
        floor_level_mm = request.args.get("floor_level_mm")
    
    if floor_level_mm is None:
        return jsonify({"error": "Missing 'floor_level_mm' in request body or query parameter"}), 400
    
    try:
        floor_level_mm = int(floor_level_mm)
        if floor_level_mm <= 0 or floor_level_mm > 5000:
            return jsonify({"error": f"Invalid floor_level_mm: {floor_level_mm}. Must be between 1 and 5000 mm"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": f"Invalid floor_level_mm value: {floor_level_mm}. Must be an integer"}), 400
    
    # Update database
    success = update_cabin_minimum_distance(cabin_id_db, floor_level_mm)
    if not success:
        return jsonify({"error": "Failed to update floor level in database"}), 500
    
    current_app.logger.info(f"Updated floor level for {cabin_id_db} to {floor_level_mm}mm (manual set)")
    
    # Optional: Also send to firmware via MQTT command (if firmware supports it)
    # This would be: {"set_floor_level": 450}
    presence_service = current_app.config.get("PRESENCE_SERVICE")
    if presence_service:
        try:
            broker = presence_service.broker
            port = presence_service.port
            username = presence_service.username
            password = presence_service.password
            site = presence_service.site or "garage-01"
            topic_base = presence_service.topic_base or "parking"
            
            # Send command to firmware to update its stored floor level
            command_topic = f"{topic_base}/{site}/{cabin_id_mqtt}/cmd"
            command_payload = json.dumps({"set_floor_level": floor_level_mm})
            
            client = mqtt.Client(client_id=f"kiosko-set-floor-{int(time.time())}")
            if username and password:
                client.username_pw_set(username, password)
            
            client.connect(broker, port, 60)
            client.publish(command_topic, command_payload, qos=1, retain=False)
            client.disconnect()
            
            current_app.logger.info(f"Sent set_floor_level command to {cabin_id_mqtt} firmware via MQTT")
        except Exception as e:
            current_app.logger.warning(f"Failed to send floor level to firmware: {e}")
            # Don't fail the request if firmware update fails - DB update succeeded
    
    return jsonify({
        "success": True,
        "message": f"Floor level set to {floor_level_mm}mm for {cabin_id_db}",
        "cabin_id": cabin_id_db,
        "floor_level_mm": floor_level_mm
    }), 200


@bp.route("/cabin/move-to-floor", methods=["POST"])
def move_cabin_to_floor():
    """Send MQTT command to move cabin to floor level.
    
    Request body (JSON):
    {
        "cabin_id": "cabina-01"
    }
    
    Returns:
        JSON with success status
    """
    data = request.get_json()
    if not data or "cabin_id" not in data:
        return jsonify({"error": "Missing 'cabin_id' in request body"}), 400
    
    cabin_id = data.get("cabin_id")
    presence_service = current_app.config.get("PRESENCE_SERVICE")
    
    if not presence_service:
        return jsonify({"error": "Presence service unavailable"}), 503
    
    try:
        # Get MQTT configuration from presence service
        broker = presence_service.broker
        port = presence_service.port
        username = presence_service.username
        password = presence_service.password
        site = presence_service.site or "garage-01"
        topic_base = presence_service.topic_base or "parking"
        
        # Construct command topic: parking/{site}/{cabin_id}/command/move-to-floor
        command_topic = f"{topic_base}/{site}/{cabin_id}/command/move-to-floor"
        
        # Create MQTT client for publishing
        client = mqtt.Client(client_id=f"kiosko-command-{int(time.time())}")
        
        if username and password:
            client.username_pw_set(username, password)
        
        # Connect and publish
        client.connect(broker, port, 60)
        client.publish(command_topic, "1", qos=1, retain=False)
        client.disconnect()
        
        current_app.logger.info(f"Sent move-to-floor command for {cabin_id} via MQTT topic: {command_topic}")
        
        return jsonify({
            "success": True,
            "message": f"Move-to-floor command sent for {cabin_id}",
            "topic": command_topic
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error sending move-to-floor command: {e}", exc_info=True)
        return jsonify({"error": f"Failed to send command: {str(e)}"}), 500


@bp.route("/camera/scan", methods=["POST"])
def camera_scan():
    """Process a scanned QR code token, validate ticket, set active cabin, and move to floor.
    
    Request body (JSON):
    {
        "token": "PARKING:uuid-here" or "uuid-here"
    }
    
    Returns:
        JSON with ticket information, cabin info, and processing status
    """
    data = request.get_json()
    if not data or "token" not in data:
        return jsonify({"error": "Missing 'token' in request body"}), 400
    
    token = data.get("token")
    
    # Handle "PARKING:uuid" format
    if token.startswith("PARKING:"):
        token = token[8:]  # Remove "PARKING:" prefix
    
    # Look up ticket in database
    ticket = get_ticket_by_token(token)
    if not ticket:
        return jsonify({
            "success": False,
            "error": "Ticket not found",
            "token": token
        }), 404
    
    cabin_id = ticket["cabina_id"]
    current_app.logger.info(f"QR code scanned: token={token}, cabin={cabin_id}")
    
    # Set active cabin
    presence_service = current_app.config.get("PRESENCE_SERVICE")
    if presence_service:
        success = presence_service.set_active_cabin(cabin_id)
        if success:
            current_app.logger.info(f"Active cabin set to {cabin_id}")
        else:
            current_app.logger.warning(f"Failed to set active cabin to {cabin_id}")
    else:
        current_app.logger.warning("Presence service not available, cannot set active cabin")
    
    # Send move-to-floor command
    move_success = False
    try:
        # Get MQTT configuration from presence service
        if presence_service:
            broker = presence_service.broker
            port = presence_service.port
            username = presence_service.username
            password = presence_service.password
            site = presence_service.site or "garage-01"
            topic_base = presence_service.topic_base or "parking"
            
            # Construct command topic: parking/{site}/{cabin_id}/command/move-to-floor
            command_topic = f"{topic_base}/{site}/{cabin_id}/command/move-to-floor"
            
            # Create MQTT client for publishing
            client = mqtt.Client(client_id=f"kiosko-command-{int(time.time())}")
            
            if username and password:
                client.username_pw_set(username, password)
            
            # Connect and publish
            client.connect(broker, port, 60)
            client.publish(command_topic, "1", qos=1, retain=False)
            client.disconnect()
            
            move_success = True
            current_app.logger.info(f"Move-to-floor command sent for {cabin_id} via MQTT topic: {command_topic}")
    except Exception as e:
        current_app.logger.error(f"Error sending move-to-floor command: {e}", exc_info=True)
    
    # Return ticket information with processing status
    return jsonify({
        "success": True,
        "ticket": {
            "id": ticket["id"],
            "token": ticket["token"],
            "cabina_id": cabin_id,
            "entry_timestamp": ticket["entry_timestamp"],
            "status": ticket["status"]
        },
        "cabin": {
            "id": cabin_id,
            "active_set": presence_service is not None and (presence_service.get_active_cabin() == cabin_id if presence_service else False),
            "move_to_floor_sent": move_success
        },
        "message": f"Ticket found for {cabin_id}. Active cabin set and move-to-floor command sent."
    }), 200


def _format_timestamp(ts_value):
    """Format timestamp to ISO string, handling both numeric and ISO string inputs."""
    if not ts_value:
        return None
    
    # If already a string (ISO format), return as-is
    if isinstance(ts_value, str):
        return ts_value
    
    # If numeric, convert to ISO format
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(ts_value)))
    except (ValueError, TypeError, OSError):
        return None


def _is_at_floor(current_distance: Optional[int], minimum_distance: Optional[int], tolerance: int = 10) -> bool:
    """Determine if cabin is at floor level based on distance comparison.
    
    Cabin is at floor when current distance is equal or less than the floor level.
    (Smaller number = closer to sensor = at floor)
    
    Args:
        current_distance: Current distance reading in mm (None if unavailable)
        minimum_distance: Minimum distance (floor level) in mm (None if not calibrated)
        tolerance: Tolerance in mm (not used, kept for compatibility)
        
    Returns:
        True if cabin is at floor level (current_distance <= minimum_distance), False otherwise
    """
    if current_distance is None or minimum_distance is None:
        return False
    
    # Cabin is at floor if current distance is equal or less than floor level
    # (smaller number = closer to sensor = at floor)
    return current_distance <= minimum_distance


@bp.route("/dashboard/cabins", methods=["GET"])
def dashboard_cabins():
    """Get all cabins from database with their current sensor status.
    
    Combines cabin database information (id, estado) with real-time sensor
    data from MQTT to provide a complete dashboard view.
    
    Returns:
        JSON with cabins array containing both DB and sensor data
    """
    try:
        # Get all cabins from database
        db_cabins = list(get_all_cabins())
        
        # Convert DB format (CABINA-01) to MQTT format (cabina-01) for sensor lookup
        cabin_ids_mqtt = []
        cabin_map = {}  # Maps DB format to MQTT format
        
        for cabin_row in db_cabins:
            db_id = cabin_row["id"]  # "CABINA-01"
            # Convert to MQTT format
            if db_id.startswith("CABINA-"):
                mqtt_id = db_id.replace("CABINA-", "cabina-").lower()
            else:
                mqtt_id = f"cabina-{db_id.zfill(2)}"
            cabin_ids_mqtt.append(mqtt_id)
            cabin_map[mqtt_id] = db_id
        
        # Get sensor data for all cabins
        # Use existing sensor check logic but adapted for all cabins
        broker = os.getenv("KIOSKO_MQTT_HOST", os.getenv("MQTT_BROKER", "127.0.0.1"))
        port = int(os.getenv("KIOSKO_MQTT_PORT", os.getenv("MQTT_PORT", "1883")))
        username = os.getenv("KIOSKO_MQTT_USER", os.getenv("MQTT_USER"))
        password = os.getenv("KIOSKO_MQTT_PASSWORD", os.getenv("MQTT_PASSWORD"))
        topic_base = os.getenv("KIOSKO_TOPIC_BASE", os.getenv("TOPIC_BASE", "parking"))
        site = os.getenv("KIOSKO_SITE_ID", os.getenv("SITE_ID", "garage-01"))
        
        sensor_results = {}
        messages_received = {}
        lock = threading.Lock()
        connection_event = threading.Event()
        timeout_event = threading.Event()
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                connection_event.set()
                for cabin_mqtt in cabin_ids_mqtt:
                    device_id = cabin_mqtt
                    topic_entry = f"{topic_base}/{site}/{device_id}/presence/entry"
                    topic_full = f"{topic_base}/{site}/{device_id}/presence/full"
                    topic_distance = f"{topic_base}/{site}/{device_id}/distance/event"
                    client.subscribe(topic_entry, qos=1)
                    client.subscribe(topic_full, qos=1)
                    client.subscribe(topic_distance, qos=0)  # Distance is QoS 0
            else:
                logger.error("MQTT connection failed with rc=%s", rc)
        
        def on_message(client, userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                device = payload.get("device", "")
                sensor = payload.get("sensor", "")
                present = bool(payload.get("present", False))
                ts = payload.get("ts")
                
                cabin_mqtt = None
                if device.startswith("cabina-"):
                    cabin_mqtt = device
                else:
                    parts = msg.topic.split("/")
                    if len(parts) >= 3:
                        device_part = parts[2]
                        if device_part.startswith("cabina-"):
                            cabin_mqtt = device_part
                
                if not cabin_mqtt or cabin_mqtt not in cabin_ids_mqtt:
                    return
                
                with lock:
                    if cabin_mqtt not in sensor_results:
                        sensor_results[cabin_mqtt] = {
                            "entry": {"present": False, "ts": None},
                            "full": {"present": False, "ts": None},
                            "distance": {"mm": None, "ts": None},
                        }
                    
                    # Handle distance messages
                    if "distance" in msg.topic:
                        to_mm = payload.get("to_mm")
                        if to_mm is not None:
                            distance_mm = int(to_mm)
                            distance_data = {"mm": distance_mm, "ts": ts}
                            sensor_results[cabin_mqtt]["distance"] = distance_data
                            
                            # Store in cache and update minimum distance
                            with _distance_cache_lock:
                                cached = _distance_cache.get(cabin_mqtt, {})
                                current_min = cached.get("min_mm")
                                # Also check database for minimum distance
                                db_id = cabin_map.get(cabin_mqtt)
                                db_min = None
                                if db_id:
                                    try:
                                        cabin_db = get_cabin(db_id)
                                        if cabin_db:
                                            try:
                                                db_min = cabin_db["minimum_distance"]
                                            except (KeyError, IndexError):
                                                pass
                                    except Exception:
                                        pass
                                
                                # ALWAYS use database value as source of truth - NEVER auto-update
                                # Floor level must be set manually via API or calibration only
                                # This prevents floor level from changing when cabin moves
                                
                                # Database value always wins - never use smaller values from cache
                                if db_min is not None:
                                    best_min = db_min  # Database is authoritative
                                elif current_min is not None:
                                    best_min = current_min  # Use cache only if DB has no value
                                else:
                                    best_min = None
                                
                                # NEVER auto-update minimum_distance - only use stored value
                                distance_data["min_mm"] = best_min
                                _distance_cache[cabin_mqtt] = distance_data
                            messages_received[f"{cabin_mqtt}/distance"] = True
                    elif sensor == "ir1" or "entry" in msg.topic:
                        sensor_results[cabin_mqtt]["entry"] = {"present": present, "ts": ts}
                        messages_received[f"{cabin_mqtt}/entry"] = True
                    elif sensor == "ir2" or "full" in msg.topic:
                        sensor_results[cabin_mqtt]["full"] = {"present": present, "ts": ts}
                        messages_received[f"{cabin_mqtt}/full"] = True
                    
                    # Update expected count - distance is optional (non-retained), so we don't require it
                    expected_count = len(cabin_ids_mqtt) * 2
                    if len(messages_received) >= expected_count:
                        timeout_event.set()
            except Exception as e:
                logger.warning("Error processing MQTT message: %s", e)
        
        # Get active cabin for reference
        presence_service = current_app.config.get("PRESENCE_SERVICE")
        active_cabin_mqtt = None
        if presence_service:
            active_cabin_db = presence_service.get_active_cabin()
            if active_cabin_db:
                # Normalize to match our format
                if active_cabin_db.startswith("CABINA-"):
                    active_cabin_mqtt = active_cabin_db.replace("CABINA-", "cabina-").lower()
                elif active_cabin_db.startswith("cabina-"):
                    active_cabin_mqtt = active_cabin_db.lower()
            
            # Populate sensor data from presence service state (it maintains state for all cabins continuously)
            # This is the PRIMARY source - more reliable than temporary MQTT connection
            presence_data_available = False
            try:
                if hasattr(presence_service, '_state') and hasattr(presence_service, '_lock'):
                    with presence_service._lock:
                        for cabin_id, cabin_state in presence_service._state.items():
                            if isinstance(cabin_state, dict):
                                # Get IR sensor data
                                entry_data = cabin_state.get("entry", {})
                                full_data = cabin_state.get("full", {})
                                distance_data = cabin_state.get("distance", {})
                                
                                # Update sensor_results with data from PresenceService
                                if cabin_id not in sensor_results:
                                    sensor_results[cabin_id] = {
                                        "entry": {"present": False, "ts": None},
                                        "full": {"present": False, "ts": None},
                                        "distance": {"mm": None, "ts": None},
                                    }
                                
                                # Update entry sensor if available
                                if entry_data.get("present") is not None or entry_data.get("ts"):
                                    sensor_results[cabin_id]["entry"] = {
                                        "present": bool(entry_data.get("present", False)),
                                        "ts": entry_data.get("ts")
                                    }
                                    presence_data_available = True
                                
                                # Update full sensor if available
                                if full_data.get("present") is not None or full_data.get("ts"):
                                    sensor_results[cabin_id]["full"] = {
                                        "present": bool(full_data.get("present", False)),
                                        "ts": full_data.get("ts")
                                    }
                                    presence_data_available = True
                                
                                # Update distance if available
                                to_mm = distance_data.get("to_mm")
                                if to_mm is not None:
                                    sensor_results[cabin_id]["distance"] = {
                                        "mm": int(to_mm),
                                        "ts": distance_data.get("ts")
                                    }
                                    # Also update distance cache
                                    with _distance_cache_lock:
                                        _distance_cache[cabin_id] = {
                                            "mm": int(to_mm),
                                            "ts": distance_data.get("ts")
                                        }
            except Exception as e:
                logger.debug("Could not populate sensor data from presence service: %s", e)
        
        # Get sensor data via MQTT (with timeout if MQTT unavailable)
        client = mqtt.Client(client_id=f"kiosko-dashboard-{int(time.time())}", clean_session=True)
        if username:
            client.username_pw_set(username, password)
        
        client.on_connect = on_connect
        client.on_message = on_message
        
        sensor_data_available = False
        try:
            client.connect(broker, port, keepalive=30)
            client.loop_start()
            
            if connection_event.wait(timeout=5):
                timeout_event.wait(timeout=3)
                time.sleep(0.5)
                sensor_data_available = True
            else:
                current_app.logger.warning("MQTT connection timeout for dashboard")
            
            client.loop_stop()
            client.disconnect()
        except Exception as e:
            current_app.logger.warning("MQTT not available for dashboard: %s", e)
            try:
                client.loop_stop()
                client.disconnect()
            except:
                pass
        
        # Combine database and sensor data
        cabins_data = []
        for cabin_row in db_cabins:
            db_id = cabin_row["id"]
            estado = cabin_row["estado"]
            # sqlite3.Row supports dictionary access with [], not .get() method
            try:
                updated_at = cabin_row["updated_at"]
            except (KeyError, IndexError):
                updated_at = None
            
            # Get minimum distance from database (floor level)
            try:
                minimum_distance = cabin_row["minimum_distance"]
            except (KeyError, IndexError):
                minimum_distance = None
            
            # Get corresponding MQTT ID
            if db_id.startswith("CABINA-"):
                mqtt_id = db_id.replace("CABINA-", "cabina-").lower()
            else:
                mqtt_id = f"cabina-{db_id.zfill(2)}"
            
            # Get sensor data from MQTT results
            sensor_info = sensor_results.get(mqtt_id, {})
            entry_sensor = sensor_info.get("entry", {"present": False, "ts": None})
            full_sensor = sensor_info.get("full", {"present": False, "ts": None})
            distance_sensor = sensor_info.get("distance", {"mm": None, "ts": None})
            
            # Initialize minimum distance from database
            min_distance_from_db = minimum_distance
            
            # Initialize cache with minimum distance from database if not already set
            with _distance_cache_lock:
                if mqtt_id not in _distance_cache:
                    _distance_cache[mqtt_id] = {}
                if _distance_cache[mqtt_id].get("min_mm") is None and min_distance_from_db is not None:
                    _distance_cache[mqtt_id]["min_mm"] = min_distance_from_db
            
            # If no distance from MQTT, check persistent cache
            if distance_sensor.get("mm") is None:
                with _distance_cache_lock:
                    cached_distance = _distance_cache.get(mqtt_id)
                    if cached_distance:
                        distance_sensor = cached_distance.copy()
                        # Ensure minimum is set
                        if distance_sensor.get("min_mm") is None:
                            distance_sensor["min_mm"] = min_distance_from_db
            
            # Also check presence service cache for distance data (fallback)
            if distance_sensor.get("mm") is None and presence_service:
                try:
                    # Get snapshot from presence service for this cabin
                    snapshot = presence_service.snapshot(cabin_id=mqtt_id) if hasattr(presence_service, 'snapshot') else None
                    if snapshot and snapshot.get("distance"):
                        cached_distance = snapshot["distance"]
                        cached_to_mm = cached_distance.get("to_mm")
                        if cached_to_mm is not None:
                            # Convert cached distance to our format and store in cache
                            distance_sensor = {
                                "mm": int(cached_to_mm),
                                "ts": cached_distance.get("ts"),
                                "min_mm": min_distance_from_db
                            }
                            with _distance_cache_lock:
                                _distance_cache[mqtt_id] = distance_sensor
                except Exception as e:
                    current_app.logger.debug("Could not get cached distance from presence service: %s", e)
            
            # Ensure minimum distance is set (from cache, DB, or None)
            if distance_sensor.get("min_mm") is None:
                distance_sensor["min_mm"] = min_distance_from_db
            
            # Determine overall state
            # Use PresenceService data if available (more reliable), otherwise fall back to MQTT temp connection
            if presence_data_available or sensor_data_available:
                if full_sensor.get("present", False):
                    sensor_state = "occupied"
                    sensor_message = "Vehículo detectado"
                elif entry_sensor.get("present", False):
                    sensor_state = "transitioning"
                    sensor_message = "Vehículo ingresando..."
                else:
                    sensor_state = "free"
                    sensor_message = "Espacio libre"
            else:
                sensor_state = "unknown"
                sensor_message = "Sensor no disponible"
            
            is_active = (mqtt_id == active_cabin_mqtt) if active_cabin_mqtt else False
            
            # Check calibration status
            motor_service = current_app.config.get("MOTOR_CONTROL_SERVICE")
            is_calibrating = False
            if motor_service:
                is_calibrating = motor_service.is_calibrating(mqtt_id)
            
            cabin_data = {
                "id": db_id,
                "id_mqtt": mqtt_id,
                "estado": estado,
                "updated_at": updated_at,
                "is_active": is_active,
                "calibrating": is_calibrating,
                "sensors": {
                    "entry": {
                        "present": entry_sensor.get("present", False),
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry_sensor["ts"])) if entry_sensor.get("ts") else None,
                    },
                    "full": {
                        "present": full_sensor.get("present", False),
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(full_sensor["ts"])) if full_sensor.get("ts") else None,
                    },
                    "distance": {
                        "mm": distance_sensor.get("mm"),
                        "min_mm": distance_sensor.get("min_mm") if distance_sensor.get("min_mm") is not None else minimum_distance,
                        "ts": _format_timestamp(distance_sensor.get("ts")),
                    },
                },
                "sensor_state": sensor_state,
                "sensor_message": sensor_message,
                "sensor_data_available": sensor_data_available,
                "is_at_floor": _is_at_floor(
                    distance_sensor.get("mm"),
                    distance_sensor.get("min_mm") if distance_sensor.get("min_mm") is not None else minimum_distance
                ),
            }
            cabins_data.append(cabin_data)
        
        return jsonify({
            "cabins": cabins_data,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "active_cabin": active_cabin_mqtt,
        })
        
    except Exception as e:
        current_app.logger.exception("Error getting dashboard cabins: %s", e)
        return jsonify({"error": f"Failed to get dashboard data: {str(e)}"}), 500


@bp.route("/db/cleanup", methods=["POST"])
def db_cleanup():
    """Clean up database: delete tickets and/or reset cabins.
    
    This endpoint allows resetting the database to a clean state.
    Requires confirmation in the request body to prevent accidental cleanup.
    
    Request body (JSON):
    {
        "confirm": true,  // Required: must be true to proceed
        "tickets": true,  // Optional: delete all tickets (default: false)
        "cabins": true,   // Optional: reset all cabins to 'free' (default: false)
        "all": true       // Optional: cleanup everything (overrides tickets/cabins)
    }
    
    Returns:
        JSON with cleanup results
    """
    data = request.get_json() or {}
    
    # Require explicit confirmation
    if not data.get("confirm") is True:
        return jsonify({
            "success": False,
            "error": "Confirmation required. Set 'confirm': true in request body."
        }), 400
    
    try:
        cleanup_all_flag = data.get("all", False)
        cleanup_tickets_flag = data.get("tickets", False)
        cleanup_cabins_flag = data.get("cabins", False)
        
        # If 'all' is true, cleanup everything
        if cleanup_all_flag:
            result = cleanup_all()
            current_app.logger.info(f"Database cleanup (all): {result}")
            return jsonify({
                "success": True,
                "message": "Database cleaned up successfully",
                "tickets_deleted": result["tickets_deleted"],
                "cabins_reset": result["cabins_reset"]
            }), 200
        
        # Otherwise, perform selective cleanup
        tickets_count = 0
        cabins_count = 0
        
        if cleanup_tickets_flag:
            tickets_count = cleanup_tickets()
            current_app.logger.info(f"Cleaned up {tickets_count} tickets")
        
        if cleanup_cabins_flag:
            cabins_count = reset_cabins()
            current_app.logger.info(f"Reset {cabins_count} cabins to 'free'")
        
        if not cleanup_tickets_flag and not cleanup_cabins_flag:
            return jsonify({
                "success": False,
                "error": "No cleanup action specified. Set 'tickets': true, 'cabins': true, or 'all': true"
            }), 400
        
        return jsonify({
            "success": True,
            "message": "Cleanup completed successfully",
            "tickets_deleted": tickets_count,
            "cabins_reset": cabins_count
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error during database cleanup: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Cleanup failed: {str(e)}"
        }), 500