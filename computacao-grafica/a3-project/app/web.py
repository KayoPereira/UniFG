from __future__ import annotations

import base64
import binascii
from datetime import datetime
from functools import wraps
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from .config import settings
from .database import (
    get_dashboard_metrics,
    init_database,
    list_admin_users,
    list_attendance_logs,
    list_employees,
)
from .services.attendance_service import AttendanceService, LivenessCheckError
from .services.auth_service import AuthService


def format_iso_datetime(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone().strftime("%d/%m/%Y %H:%M:%S")


def decode_data_url_image(data_url: str) -> bytes:
    if not isinstance(data_url, str) or not data_url.strip():
        raise ValueError("Imagem ausente no payload recebido.")

    encoded_data = data_url.split(",", 1)[1] if "," in data_url else data_url

    try:
        return base64.b64decode(encoded_data)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Falha ao decodificar a imagem enviada pelo navegador.") from exc


def parse_captures(payload: dict[str, Any], minimum_images: int) -> list[bytes]:
    captures = payload.get("captures")
    if not isinstance(captures, list) or len(captures) < minimum_images:
        raise ValueError(
            f"Envie pelo menos {minimum_images} capturas para concluir esta operacao."
        )
    return [decode_data_url_image(capture) for capture in captures]


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(settings.base_dir / "templates"),
        static_folder=str(settings.base_dir / "static"),
    )
    app.secret_key = settings.secret_key
    init_database()
    attendance_service = AttendanceService()
    auth_service = AuthService()

    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("admin_email"):
                return redirect(url_for("auth_login"))
            return f(*args, **kwargs)
        return decorated

    @app.template_filter("datetime_br")
    def datetime_br(value: str) -> str:
        return format_iso_datetime(value)

    # --- Páginas públicas ---

    @app.get("/")
    def index() -> str:
        metrics = get_dashboard_metrics()
        return render_template("index.html", metrics=metrics)

    @app.get("/entrada")
    def entrada() -> str:
        return render_template("entrada.html", settings=settings)

    @app.get("/saida")
    def saida() -> str:
        return render_template("saida.html", settings=settings)

    # --- Autenticação ---

    @app.route("/auth/login", methods=["GET", "POST"])
    def auth_login():
        if session.get("admin_email"):
            return redirect(url_for("admin"))

        error = None
        if request.method == "POST":
            email = request.form.get("email", "")
            password = request.form.get("password", "")
            user = auth_service.authenticate(email, password)
            if user:
                session["admin_email"] = user["email"]
                return redirect(url_for("admin"))
            error = "Email ou senha incorretos."

        return render_template("auth/login.html", error=error)

    @app.get("/auth/logout")
    def auth_logout():
        session.clear()
        return redirect(url_for("auth_login"))

    # --- Admin (protegido) ---

    @app.get("/admin")
    @login_required
    def admin() -> str:
        employees = list_employees()
        logs = list_attendance_logs()
        admin_users = list_admin_users()
        return render_template(
            "admin.html",
            employees=employees,
            logs=logs,
            admin_users=admin_users,
            settings=settings,
        )

    @app.post("/admin/usuarios")
    @login_required
    def admin_create_user():
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        try:
            auth_service.register(email, password)
            return redirect(url_for("admin") + "#usuarios")
        except ValueError as exc:
            employees = list_employees()
            logs = list_attendance_logs()
            admin_users = list_admin_users()
            return render_template(
                "admin.html",
                employees=employees,
                logs=logs,
                admin_users=admin_users,
                settings=settings,
                user_error=str(exc),
            ), 422

    # --- APIs ---

    @app.post("/api/employees")
    def create_employee_route():
        payload = request.get_json(silent=True) or {}

        try:
            employee = attendance_service.register_employee(
                employee_code=str(payload.get("employee_code", "")).strip(),
                full_name=str(payload.get("full_name", "")).strip(),
                department=str(payload.get("department", "")).strip() or None,
                images=parse_captures(payload, settings.web_enrollment_samples),
            )
        except (ValueError, RuntimeError) as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        return jsonify(
            {
                "status": "success",
                "message": f"Funcionario {employee['full_name']} cadastrado com sucesso.",
                "employee": employee,
            }
        ), 201

    @app.post("/api/attendance/angle")
    def get_tilt_angle_route():
        payload = request.get_json(silent=True) or {}
        try:
            images = parse_captures(payload, 1)
            angle = attendance_service.get_head_tilt_angle(images)
        except (ValueError, RuntimeError):
            angle = None
        return jsonify({"angle": angle})

    @app.post("/api/attendance/scan")
    def scan_attendance_route():
        payload = request.get_json(silent=True) or {}
        requested_mode = str(payload.get("mode", "")).strip().lower()

        if requested_mode not in {"entry", "exit"}:
            return jsonify({"status": "error", "message": "Modo invalido. Use entry ou exit."}), 400

        try:
            outcome = attendance_service.scan_for_recognition(
                images=parse_captures(payload, 1),
                event_type=requested_mode,
            )
        except ValueError as exc:
            return jsonify({"status": "denied", "message": str(exc)}), 409
        except RuntimeError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        status_code = 200 if outcome["status"] == "recognized" else 404
        return jsonify(outcome), status_code

    @app.post("/api/attendance/confirm")
    def confirm_attendance_route():
        payload = request.get_json(silent=True) or {}
        requested_mode = str(payload.get("mode", "")).strip().lower()
        employee_code = str(payload.get("employee_code", "")).strip()

        if requested_mode not in {"entry", "exit"} or not employee_code:
            return jsonify({"status": "error", "message": "Payload invalido."}), 400

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        try:
            outcome = attendance_service.confirm_with_liveness(
                images=parse_captures(payload, 1),
                employee_code=employee_code,
                event_type=requested_mode,
                confidence=confidence,
            )
        except LivenessCheckError as exc:
            return jsonify({
                "status": "liveness_failed",
                "message": str(exc),
                "angle": exc.angle,
            }), 422
        except ValueError as exc:
            return jsonify({"status": "denied", "message": str(exc)}), 409
        except RuntimeError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        return jsonify(outcome), 200

    return app
