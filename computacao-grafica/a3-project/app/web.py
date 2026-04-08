from __future__ import annotations

from datetime import datetime

from flask import Flask, render_template

from .config import settings
from .database import get_dashboard_metrics, init_database, list_attendance_logs, list_employees


def format_iso_datetime(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone().strftime("%d/%m/%Y %H:%M:%S")


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(settings.base_dir / "templates"),
        static_folder=str(settings.base_dir / "static"),
    )
    init_database()

    @app.template_filter("datetime_br")
    def datetime_br(value: str) -> str:
        return format_iso_datetime(value)

    @app.get("/")
    def index() -> str:
        metrics = get_dashboard_metrics()
        employees = list_employees()
        logs = list_attendance_logs()
        return render_template(
            "index.html",
            metrics=metrics,
            employees=employees,
            logs=logs,
        )

    return app
