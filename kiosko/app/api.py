"""Lightweight JSON API for kiosk front-end widgets."""
from flask import Blueprint, current_app, jsonify


bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/presence", methods=["GET"])
def presence_status():
    service = current_app.config.get("PRESENCE_SERVICE")
    if not service:
        return jsonify({"error": "presence service unavailable"}), 503
    return jsonify(service.snapshot())
