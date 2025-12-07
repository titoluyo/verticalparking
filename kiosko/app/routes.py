"""
Flask routes for the kiosk home screen.
Currently exposes simple actions for storing or retrieving vehicles.
"""
import uuid
import logging
from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, Response
from .database import (
    create_ticket, update_cabin_status, find_free_cabin, get_cabin,
    get_ticket_by_token, find_next_free_cabin_circular, get_next_cabin_circular,
    has_active_ticket, update_cabin_minimum_distance
)

# Module-level logger for MQTT callbacks (they run in separate threads)
logger = logging.getLogger(__name__)


bp = Blueprint("routes", __name__)


@bp.route("/")
def index():
    """Landing page with the main kiosk actions."""
    return render_template("index.html")


@bp.route("/guardar", methods=["GET", "POST"])
def guardar_vehiculo():
    """Store a vehicle: assign cabin, create ticket, and print."""
    if request.method == "GET":
        return render_template("guardar.html")
    
    # POST: Process vehicle storage
    try:
        # Get presence service to access active cabin
        presence_service = current_app.config.get("PRESENCE_SERVICE")
        if not presence_service:
            flash("Servicio de presencia no disponible", "error")
            return render_template("guardar.html", error="Servicio no disponible")
        
        # Get active cabin
        active_cabin = presence_service.get_active_cabin()
        if not active_cabin:
            flash("No hay cabina activa configurada", "error")
            return render_template("guardar.html", error="No hay cabina activa")
        
        # Normalize cabin ID format (ensure it matches DB format: CABINA-01)
        if active_cabin.startswith("cabina-"):
            active_cabin = active_cabin.replace("cabina-", "CABINA-").upper()
        elif not active_cabin.startswith("CABINA-"):
            active_cabin = f"CABINA-{active_cabin.zfill(2)}"
        
        # Check if active cabin is free, if not, find a free one
        cabin = get_cabin(active_cabin)
        if not cabin:
            flash(f"Cabina {active_cabin} no encontrada en la base de datos", "error")
            return render_template("guardar.html", error="Cabina no encontrada")
        
        # Check if active cabin is free or can be used (no active ticket)
        if cabin["estado"] != "free":
            # Check if cabin actually has an active ticket
            if has_active_ticket(active_cabin):
                # Cabin has active ticket, find next free cabin in circular order
                current_app.logger.info(f"Active cabin {active_cabin} is busy with active ticket, finding next free cabin in circular order")
                free_cabin_id = find_next_free_cabin_circular(active_cabin, logger=current_app.logger)
                if not free_cabin_id:
                    current_app.logger.error(f"No free cabins found when searching from {active_cabin}")
                    flash("No hay cabinas disponibles en este momento", "error")
                    return render_template("guardar.html", error="No hay cabinas disponibles")
                else:
                    active_cabin = free_cabin_id
                    current_app.logger.info(f"Using free cabin: {active_cabin}")
            else:
                # Cabin is marked busy but has no active ticket - treat as free
                current_app.logger.info(f"Active cabin {active_cabin} is marked busy but has no active ticket, treating as free")
                # Reset cabin status to free
                update_cabin_status(active_cabin, "free")
        
        # Generate unique token for QR code
        token = str(uuid.uuid4())
        
        # Create ticket in database
        ticket_id = create_ticket(
            token=token,
            cabina_id=active_cabin,
            vehicle_plate=None  # Can be added later if needed
        )
        
        if not ticket_id:
            flash("Error al crear el ticket en la base de datos", "error")
            return render_template("guardar.html", error="Error al crear ticket")
        
        # Update cabin status to busy
        if not update_cabin_status(active_cabin, "busy"):
            current_app.logger.error(f"Failed to update cabin {active_cabin} status to busy")
            flash("Error al actualizar estado de la cabina", "error")
            return render_template("guardar.html", error="Error al actualizar cabina")
        
        # Print ticket
        printer_service = current_app.config.get("PRINTER_SERVICE")
        if printer_service:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Use short ID for display, full token for QR code
            print_success = printer_service.print_entry_ticket(
                vehicle_plate="",  # Not used in current design
                cabin_id=active_cabin,
                timestamp=timestamp,
                ticket_id=token[:8].upper(),  # Short ID for display
                token=token  # Full token for QR code
            )
            if not print_success:
                current_app.logger.warning("Failed to print ticket, but ticket was saved")
                flash("Ticket guardado pero no se pudo imprimir", "warning")
        else:
            current_app.logger.warning("Printer service not available")
            flash("Ticket guardado pero impresora no disponible", "warning")
        
        # Find next free cabin in circular order and move it to floor level
        # Start searching from the next cabin in circular order after the one we just assigned
        next_cabin_in_circle = get_next_cabin_circular(active_cabin)
        next_free_cabin = find_next_free_cabin_circular(next_cabin_in_circle, logger=current_app.logger)
        
        if next_free_cabin:
            # Convert DB format (CABINA-01) to PresenceService format (cabina-01)
            next_free_cabin_presence = next_free_cabin.replace("CABINA-", "cabina-").lower()
            
            # Get motor control service
            motor_service = current_app.config.get("MOTOR_CONTROL_SERVICE")
            current_app.logger.info(f"Motor control service available: {motor_service is not None}")
            
            # Note: We no longer need to check minimum_distance here because the cabin firmware
            # will automatically detect when it reaches floor level and publish a floor/reached event.
            # The firmware uses its stored floor level (from calibration) to detect floor arrival.
            
            # Always try to start motor if service is available
            if motor_service:
                # Store references that will be needed in the callback
                # Note: The callback runs in MQTT thread, so we need to pass services directly
                motor_service_ref = motor_service
                presence_service_ref = presence_service
                
                # Define callback to handle floor reached event
                # This callback will be called from MQTT thread, so we need to use module logger
                # and cannot use Flask's current_app context
                def on_floor_reached(cabin_id: str, event_data: dict):
                    """Callback when cabin reaches floor level (from MQTT event)."""
                    try:
                        # Convert to PresenceService format if needed
                        cabin_id_presence = cabin_id.replace("CABINA-", "cabina-").lower() if cabin_id.startswith("CABINA-") else cabin_id
                        
                        logger.info(f"Floor reached: {cabin_id_presence} (distance={event_data.get('distance_mm')}mm)")
                        
                        # CRITICAL: Stop motor
                        stop_success = motor_service_ref.stop_motor(cabin_id_presence)
                        if not stop_success:
                            logger.error(f"Failed to stop motor for {cabin_id_presence}")
                        
                        # Activate cabin
                        if presence_service_ref:
                            try:
                                presence_service_ref.set_active_cabin(cabin_id_presence)
                                logger.info(f"Activated cabin: {cabin_id_presence}")
                            except Exception as e:
                                logger.error(f"Error activating cabin {cabin_id_presence}: {e}", exc_info=True)
                        
                    except Exception as e:
                        logger.error(f"Error in on_floor_reached callback for {cabin_id}: {e}", exc_info=True)
                        # Even if there's an error, try to stop the motor as a safety measure
                        try:
                            cabin_id_presence = cabin_id.replace("CABINA-", "cabina-").lower() if cabin_id.startswith("CABINA-") else cabin_id
                            motor_service_ref.stop_motor(cabin_id_presence)
                            logger.info(f"Emergency motor stop attempted for {cabin_id_presence}")
                        except Exception as emergency_error:
                            logger.error(f"Emergency motor stop also failed: {emergency_error}")
                
                # Register floor reached callback for ANY free cabin
                # Since motor is global, multiple cabins may be descending simultaneously.
                # We accept the FIRST free cabin that reaches floor level.
                def floor_callback(cabin_id: str, event_data: dict):
                    """Callback that accepts ANY free cabin reaching floor."""
                    try:
                        # Check if this cabin is free (no active ticket) - use direct DB access
                        cabin_id_db = cabin_id.replace("cabina-", "CABINA-").upper() if not cabin_id.startswith("CABINA-") else cabin_id
                        from .database import has_active_ticket_direct
                        
                        if has_active_ticket_direct(cabin_id_db):
                            logger.debug(f"Floor event ignored for {cabin_id} - has active ticket")
                            return
                        
                        # This cabin is free and reached floor - stop motor and activate it
                        logger.info(f"Free cabin {cabin_id} reached floor - stopping motor")
                        on_floor_reached(cabin_id, event_data)
                        
                        # Unregister callback after use (one-time event)
                        try:
                            with presence_service._callbacks_lock:
                                if floor_callback in presence_service._floor_reached_callbacks:
                                    presence_service._floor_reached_callbacks.remove(floor_callback)
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"Error unregistering callback: {e}")
                    except Exception as e:
                        logger.error(f"Error in floor callback: {e}", exc_info=True)
                
                presence_service.register_floor_reached_callback(floor_callback)
                # Start motor
                current_app.logger.info(f"Starting motor to move {next_free_cabin_presence} to floor...")
                motor_started = motor_service.start_motor(next_free_cabin_presence)
                
                if motor_started:
                    # Set as active cabin (motor is moving it to floor)
                    # The cabin firmware will detect floor and publish event, which will stop motor
                    presence_service.set_active_cabin(next_free_cabin_presence)
                else:
                    current_app.logger.error(f"Failed to start motor for {next_free_cabin_presence}")
                    # Fallback: just set as active cabin
                    presence_service.set_active_cabin(next_free_cabin_presence)
            else:
                # No motor service - just set as active cabin
                current_app.logger.warning("Motor control service not available, cannot start motor")
                if presence_service.set_active_cabin(next_free_cabin_presence):
                    current_app.logger.info(f"Set next active cabin to: {next_free_cabin_presence} (no motor service)")
                else:
                    current_app.logger.warning(f"Failed to set active cabin to: {next_free_cabin_presence}")
        else:
            current_app.logger.warning("No free cabin found for next active cabin")
        
        # Success - redirect with success message
        flash(f"Vehículo guardado exitosamente en {active_cabin}. Token: {token[:8].upper()}", "success")
        return redirect(url_for("routes.index"))
        
    except Exception as e:
        current_app.logger.error(f"Error storing vehicle: {e}", exc_info=True)
        flash(f"Error al guardar vehículo: {str(e)}", "error")
        return render_template("guardar.html", error=str(e))


@bp.route("/recoger")
def recoger_vehiculo():
    """Placeholder view for retrieving a vehicle."""
    return render_template("recoger.html")


@bp.route("/dashboard")
def dashboard():
    """Dashboard page showing all cabins with their sensor status."""
    return render_template("dashboard.html")


@bp.route("/video")
def video_view():
    """Video streaming page."""
    video_service = current_app.config.get("VIDEO_STREAM_SERVICE")
    available = video_service.is_available() if video_service else False
    return render_template("video.html", video_available=available)


@bp.route("/stream.mjpg")
def video_stream():
    """MJPEG video stream endpoint."""
    video_service = current_app.config.get("VIDEO_STREAM_SERVICE")
    if not video_service or not video_service.is_available():
        return Response("Video stream not available", status=503, mimetype="text/plain")
    
    output = video_service.get_output()
    if not output:
        return Response("Video stream output not available", status=503, mimetype="text/plain")
    
    def generate():
        """Generator function for MJPEG streaming."""
        while True:
            with output.condition:
                output.condition.wait()
                frame = output.frame
            if frame:
                yield (b'--FRAME\r\n'
                       b'Content-Type: image/jpeg\r\n'
                       b'Content-Length: ' + str(len(frame)).encode() + b'\r\n'
                       b'\r\n' + frame + b'\r\n')
    
    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=FRAME'
    )
