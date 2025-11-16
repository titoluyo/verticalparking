"""Lightweight JSON API for kiosk front-end widgets."""
import json
import queue
import time

from flask import Blueprint, Response, current_app, jsonify, stream_with_context


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
