"""
Flask routes for the kiosk home screen.
Currently exposes simple actions for storing or retrieving vehicles.
"""
from flask import Blueprint, render_template


bp = Blueprint("routes", __name__)


@bp.route("/")
def index():
    """Landing page with the main kiosk actions."""
    return render_template("index.html")


@bp.route("/guardar")
def guardar_vehiculo():
    """Placeholder view for storing a vehicle."""
    return render_template("guardar.html")


@bp.route("/recoger")
def recoger_vehiculo():
    """Placeholder view for retrieving a vehicle."""
    return render_template("recoger.html")
