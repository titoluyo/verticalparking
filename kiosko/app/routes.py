"""
Flask routes and API endpoints.
- Auth: /login, /logout
- Protected views: '/', '/register'
- API: GET/POST /api/registros
"""
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    abort,
)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from .database import query, execute, get_db
from .hardware import activar_led_ok


bp = Blueprint("routes", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("routes.login"))
        return view(*args, **kwargs)

    return wrapped


@bp.before_app_request
def _ensure_db_on_request():
    # Touch DB connection once per request to ensure context.
    _ = get_db()


# ------------------- Auth ------------------- #
@bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Login form using usuarios table.
    ---
    tags: [auth]
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - name: username
        in: formData
        type: string
        required: true
      - name: password
        in: formData
        type: string
        required: true
    responses:
      200: { description: Login page }
      302: { description: Redirect after login }
    """
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            error = "Usuario y contraseña requeridos"
        else:
            rows = query(
                "SELECT id, password_hash FROM usuarios WHERE username = ?",
                (username,),
            )
            user = rows[0] if rows else None
            if not user or not check_password_hash(user["password_hash"], password):
                error = "Credenciales inválidas"
            else:
                session["user_id"] = user["id"]
                session["username"] = username
                return redirect(url_for("routes.index"))
    return render_template("login.html", error=error)


@bp.route("/logout")
def logout():
    """
    Ends session and redirects to /login
    ---
    tags: [auth]
    responses:
      302: { description: Redirect to login }
    """
    session.clear()
    return redirect(url_for("routes.login"))


# ------------------- Views ------------------- #
@bp.route("/")
@login_required
def index():
    rows = query(
        "SELECT id, nombre, placa, creado_en FROM registros ORDER BY id DESC"
    )
    return render_template("index.html", registros=list(rows))


@bp.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        placa = request.form.get("placa", "").strip().upper()
        if not nombre or not placa:
            return render_template(
                "register.html", error="Nombre y placa son requeridos"
            )
        execute("INSERT INTO registros (nombre, placa) VALUES (?, ?)", (nombre, placa))
        activar_led_ok()
        return redirect(url_for("routes.index"))
    return render_template("register.html")


# ------------------- API ------------------- #
@bp.route("/api/registros", methods=["GET"])
def api_get_registros():
    """
    Lista todos los registros
    ---
    tags: [api]
    responses:
      200:
        description: Lista de registros
        schema:
          type: array
          items:
            type: object
            properties:
              id: { type: integer }
              nombre: { type: string }
              placa: { type: string }
              creado_en: { type: string }
    """
    rows = query(
        "SELECT id, nombre, placa, creado_en FROM registros ORDER BY id DESC"
    )
    data = [dict(r) for r in rows]
    return jsonify(data)


@bp.route("/api/registros", methods=["POST"])
def api_post_registro():
    """
    Crea un registro (nombre, placa)
    ---
    tags: [api]
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [nombre, placa]
          properties:
            nombre: { type: string }
            placa: { type: string }
    responses:
      201: { description: Registro creado }
      400: { description: Datos inválidos }
    """
    data = request.get_json(silent=True) or {}
    nombre = str(data.get("nombre", "")).strip()
    placa = str(data.get("placa", "")).strip().upper()
    if not nombre or not placa:
        return jsonify({"error": "nombre y placa requeridos"}), 400
    reg_id = execute("INSERT INTO registros (nombre, placa) VALUES (?, ?)", (nombre, placa))
    activar_led_ok()
    return jsonify({"id": reg_id, "nombre": nombre, "placa": placa}), 201


# ------------------- Utility: create user ------------------- #
@bp.route("/admin/create_user", methods=["POST"])
def admin_create_user():
    """
    Utilidad mínima para crear un usuario (para bootstrap en dev).
    Not documented in Swagger intentionally.
    Body JSON: {"username":"...", "password":"..."}
    """
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username or not password:
        return jsonify({"error": "username y password requeridos"}), 400
    try:
        pwd = generate_password_hash(password)
        execute(
            "INSERT INTO usuarios (username, password_hash) VALUES (?, ?)",
            (username, pwd),
        )
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

