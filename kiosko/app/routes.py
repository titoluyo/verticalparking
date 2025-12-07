"""
Flask routes for the kiosk home screen.
Currently exposes simple actions for storing or retrieving vehicles.
"""
import uuid
from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, Response
from .database import (
    create_ticket, update_cabin_status, find_free_cabin, get_cabin,
    get_ticket_by_token, find_next_free_cabin_circular, get_next_cabin_circular,
    has_active_ticket
)


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
            
            # Get cabin info to check minimum distance (floor level)
            next_cabin_info = get_cabin(next_free_cabin)
            minimum_distance = None
            if next_cabin_info:
                try:
                    minimum_distance_value = next_cabin_info["minimum_distance"]
                    if minimum_distance_value is not None:
                        minimum_distance = int(minimum_distance_value)
                except (KeyError, IndexError, ValueError, TypeError):
                    minimum_distance = None
            
            # Get motor control service
            motor_service = current_app.config.get("MOTOR_CONTROL_SERVICE")
            current_app.logger.info(f"Motor control service available: {motor_service is not None}")
            
            # If no minimum_distance in DB, try to get current distance from presence service as fallback
            if not minimum_distance and motor_service:
                current_app.logger.info(f"No minimum distance in DB for {next_free_cabin}, checking current distance...")
                snapshot = presence_service.snapshot(cabin_id=next_free_cabin_presence)
                if isinstance(snapshot, dict):
                    distance_data = snapshot.get("distance")
                    if distance_data and isinstance(distance_data, dict):
                        current_dist = distance_data.get("mm")
                        if current_dist is not None:
                            # Use current distance as temporary minimum (assuming it's already at or near floor)
                            minimum_distance = int(current_dist)
                            current_app.logger.info(
                                f"Using current distance {minimum_distance}mm as temporary floor reference for {next_free_cabin}"
                            )
            
            # Always try to start motor if service is available
            if motor_service:
                # Define callback to activate cabin when it reaches floor
                def on_floor_reached(cabin_id: str):
                    """Callback when cabin reaches floor level."""
                    # Convert to PresenceService format if needed
                    cabin_id_presence = cabin_id.replace("CABINA-", "cabina-").lower() if cabin_id.startswith("CABINA-") else cabin_id
                    presence_service.set_active_cabin(cabin_id_presence)
                    current_app.logger.info(f"Cabin {cabin_id} reached floor - activated as active cabin")
                
                # Start motor
                current_app.logger.info(f"Starting motor to move {next_free_cabin_presence} to floor...")
                motor_started = motor_service.start_motor(next_free_cabin_presence)
                
                if motor_started:
                    current_app.logger.info(f"Motor started successfully for {next_free_cabin_presence}")
                    
                    # If we have minimum_distance, monitor and auto-stop when floor is reached
                    if minimum_distance:
                        current_app.logger.info(
                            f"Monitoring {next_free_cabin_presence} distance (target: {minimum_distance}mm ±10mm)"
                        )
                        motor_service.start_monitoring(
                            target_cabin=next_free_cabin_presence,
                            minimum_distance=minimum_distance,
                            presence_service=presence_service,
                            stop_callback=on_floor_reached,
                            tolerance=10  # 10mm tolerance for floor detection
                        )
                    else:
                        current_app.logger.warning(
                            f"No minimum distance available for {next_free_cabin_presence}, "
                            f"motor started but will not auto-stop. Monitor manually or calibrate floor level."
                        )
                    
                    # Set as active cabin (motor is moving it to floor)
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
