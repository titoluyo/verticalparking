"""
Flask routes for the kiosk home screen.
Currently exposes simple actions for storing or retrieving vehicles.
"""
import uuid
from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request
from .database import (
    create_ticket, update_cabin_status, find_free_cabin, get_cabin,
    get_ticket_by_token
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
        
        if cabin["estado"] != "free":
            # Active cabin is busy, find a free one
            current_app.logger.info(f"Active cabin {active_cabin} is busy, finding free cabin")
            free_cabin_id = find_free_cabin()
            if not free_cabin_id:
                flash("No hay cabinas disponibles en este momento", "error")
                return render_template("guardar.html", error="No hay cabinas disponibles")
            active_cabin = free_cabin_id
            current_app.logger.info(f"Using free cabin: {active_cabin}")
        
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
        
        # Find next free cabin and set it as active
        next_free_cabin = find_free_cabin()
        if next_free_cabin:
            # Convert DB format (CABINA-01) to PresenceService format (cabina-01)
            next_free_cabin_presence = next_free_cabin.replace("CABINA-", "cabina-").lower()
            if presence_service.set_active_cabin(next_free_cabin_presence):
                current_app.logger.info(f"Set next active cabin to: {next_free_cabin_presence}")
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
