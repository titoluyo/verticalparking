"""Lightweight JSON API for kiosk front-end widgets."""
import json
import os
import queue
import threading
import time

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import paho.mqtt.client as mqtt
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from .database import cleanup_tickets, reset_cabins, cleanup_all, get_ticket_by_token
from .qr_detector import QRDetector


bp = Blueprint("api", __name__, url_prefix="/api")


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
    """Check sensor status for multiple cabins (cabina-01 to cabina-07)."""
    # Get cabin range from query params or default to cabina-01 to cabina-07
    start_cabin = request.args.get("start", "cabina-01")
    end_cabin = request.args.get("end", "cabina-07")
    
    # Parse cabin numbers
    try:
        if start_cabin.startswith("cabina-") and end_cabin.startswith("cabina-"):
            start_num = int(start_cabin[7:])
            end_num = int(end_cabin[7:])
            cabins = [f"cabina-{i:02d}" for i in range(start_num, end_num + 1)]
        else:
            return jsonify({"error": "Invalid cabin format. Use cabina-01-cabina-07 format"}), 400
    except (ValueError, IndexError):
        return jsonify({"error": "Invalid cabin format. Use cabina-01-cabina-07 format"}), 400
    
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


@bp.route("/camera/scan", methods=["POST"])
def camera_scan():
    """Process a scanned QR code token and validate the ticket.
    
    Request body (JSON):
    {
        "token": "PARKING:uuid-here" or "uuid-here"
    }
    
    Returns:
        JSON with ticket information if valid, error if not found
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
    
    # Return ticket information
    return jsonify({
        "success": True,
        "ticket": {
            "id": ticket["id"],
            "token": ticket["token"],
            "cabina_id": ticket["cabina_id"],
            "entry_timestamp": ticket["entry_timestamp"],
            "status": ticket["status"]
        }
    }), 200


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