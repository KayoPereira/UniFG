from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any

from flask import Flask, jsonify, render_template, request

from .config import settings
from .database import get_dashboard_metrics, init_database, list_residents
from .services.attendance_service import AccessService


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
    init_database()
    access_service = AccessService()

    @app.template_filter("datetime_br")
    def datetime_br(value: str) -> str:
        return format_iso_datetime(value)

    @app.get("/")
    def index() -> str:
        metrics = get_dashboard_metrics() if 'get_dashboard_metrics' in globals() else {}
        residents = list_residents()
        logs = []  # Ajustar para logs de acesso se necessário
        return render_template(
            "index.html",
            metrics=metrics,
            residents=residents,
            logs=logs,
            settings=settings,
        )

    @app.post("/api/residents")
    def create_resident_route():
        payload = request.get_json(silent=True) or {}

        try:
            resident = access_service.register_resident(
                resident_code=str(payload.get("resident_code", "")).strip(),
                full_name=str(payload.get("full_name", "")).strip(),
                unit=str(payload.get("unit", "")).strip() or None,
                images=parse_captures(payload, settings.web_enrollment_samples),
            )
        except (ValueError, RuntimeError) as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        return jsonify(
            {
                "status": "success",
                "message": f"Morador/Visitante {resident['full_name']} cadastrado com sucesso.",
                "resident": resident,
            }
        ), 201

    @app.post("/api/attendance/scan")
    def scan_attendance_route():
        payload = request.get_json(silent=True) or {}
        requested_mode = str(payload.get("mode", "")).strip().lower()

        if requested_mode not in {"entry", "exit"}:
            return jsonify({"status": "error", "message": "Modo invalido. Use entry ou exit."}), 400

        try:
            outcome = attendance_service.recognize_and_log(
                images=parse_captures(payload, settings.web_scan_samples),
                event_type=requested_mode,
                source="web",
            )
        except ValueError as exc:
            return jsonify({"status": "denied", "message": str(exc)}), 409
        except RuntimeError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        status_code = 200 if outcome["status"] == "success" else 404
        return jsonify(outcome), status_code

    return app
