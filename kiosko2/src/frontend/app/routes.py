"""
Flask routes for the kiosk UI.

This is a thin UI layer that delegates business logic to the FastAPI backend.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app

bp = Blueprint("routes", __name__)


def get_backend():
    """Get the backend client from app config."""
    return current_app.config.get("BACKEND_CLIENT")


@bp.route("/")
def index():
    """Landing page with the main kiosk actions."""
    return render_template("index.html")


@bp.route("/guardar", methods=["GET", "POST"])
def guardar_vehiculo():
    """Store a vehicle: assign cabin, create ticket, and print."""
    backend = get_backend()
    
    if request.method == "GET":
        return render_template("guardar.html")
    
    # POST: Process vehicle storage
    try:
        # Get active cabin from backend
        active_cabin = backend.get_active_cabin()
        if not active_cabin:
            flash("No hay cabina activa configurada", "error")
            return render_template("guardar.html", error="No hay cabina activa")
        
        # Normalize cabin ID format
        if active_cabin.startswith("cabina-"):
            active_cabin_db = active_cabin.replace("cabina-", "CABINA-").upper()
        else:
            active_cabin_db = active_cabin
        
        # Create ticket via backend
        result = backend.create_ticket(
            cabin_id=active_cabin_db,
            vehicle_plate="",
            print_ticket=True,
        )
        
        if not result.get("success"):
            flash(result.get("message", "Error al crear ticket"), "error")
            return render_template("guardar.html", error=result.get("message"))
        
        token = result.get("token", "")[:8].upper()
        flash(f"Vehículo guardado exitosamente en {active_cabin_db}. Token: {token}", "success")
        return redirect(url_for("routes.index"))
        
    except Exception as e:
        current_app.logger.error(f"Error storing vehicle: {e}", exc_info=True)
        flash(f"Error al guardar vehículo: {str(e)}", "error")
        return render_template("guardar.html", error=str(e))


@bp.route("/recoger", methods=["GET", "POST"])
def recoger_vehiculo():
    """Retrieve a vehicle using QR code."""
    backend = get_backend()
    
    if request.method == "GET":
        return render_template("recoger.html")
    
    # POST: Process vehicle retrieval
    try:
        token = request.form.get("token", "").strip()
        if not token:
            flash("Por favor ingrese el código del ticket", "error")
            return render_template("recoger.html", error="Código requerido")
        
        # Scan and validate ticket via backend
        result = backend.scan_ticket(token)
        
        if not result.get("success"):
            flash(result.get("message", "Ticket no válido"), "error")
            return render_template("recoger.html", error=result.get("message"))
        
        cabin_id = result.get("cabina_id", "")
        
        # Set active cabin and start motor
        if cabin_id:
            mqtt_id = cabin_id.replace("CABINA-", "cabina-").lower()
            backend.set_active_cabin(mqtt_id)
            backend.start_motor()
        
        flash(f"Vehículo en camino desde {cabin_id}", "success")
        return render_template("recoger.html", 
                             success=True, 
                             cabin_id=cabin_id,
                             message="Su vehículo está en camino. Por favor espere.")
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving vehicle: {e}", exc_info=True)
        flash(f"Error al recoger vehículo: {str(e)}", "error")
        return render_template("recoger.html", error=str(e))


@bp.route("/dashboard")
def dashboard():
    """Dashboard page showing all cabins with their sensor status."""
    backend = get_backend()
    
    try:
        cabins = backend.get_cabins()
        active_cabin = backend.get_active_cabin()
    except Exception as e:
        current_app.logger.error(f"Error loading dashboard: {e}")
        cabins = []
        active_cabin = None
    
    return render_template("dashboard.html", cabins=cabins, active_cabin=active_cabin)


@bp.route("/api/dashboard/cabins")
def api_dashboard_cabins():
    """API endpoint for dashboard cabin data (for AJAX updates)."""
    from flask import jsonify
    
    backend = get_backend()
    
    try:
        cabins = backend.get_cabins()
        active_cabin = backend.get_active_cabin()
        return jsonify({
            "cabins": cabins,
            "active_cabin": active_cabin,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
