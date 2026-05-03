from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import firebase_admin
import numpy as np
from firebase_admin import credentials, firestore

from .config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_firebase_app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        options: dict[str, str] = {}
        if settings.firebase_project_id:
            options["projectId"] = settings.firebase_project_id

        if settings.firebase_credentials_path is not None:
            if not settings.firebase_credentials_path.exists():
                raise RuntimeError(
                    "O arquivo configurado em FIREBASE_CREDENTIALS_PATH nao foi encontrado: "
                    f"{settings.firebase_credentials_path}"
                )

            credential = credentials.Certificate(str(settings.firebase_credentials_path))
            return firebase_admin.initialize_app(credential, options or None)

        if not settings.firebase_project_id:
            raise RuntimeError(
                "Defina FIREBASE_PROJECT_ID e uma credencial de servico para usar o Firestore."
            )

        try:
            return firebase_admin.initialize_app(options=options or None)
        except Exception as exc:
            raise RuntimeError(
                "Nao foi possivel inicializar o Firebase. Defina FIREBASE_CREDENTIALS_PATH com o JSON da conta de servico."
            ) from exc


def _get_firestore_client() -> firestore.Client:
    return firestore.client(app=_get_firebase_app())


def _employees_collection():
    return _get_firestore_client().collection("employees")


def _attendance_collection():
    return _get_firestore_client().collection("attendance_logs")


def _validate_employee_code(employee_code: str) -> None:
    invalid_chars = ".#$[]/"
    if any(char in employee_code for char in invalid_chars):
        raise ValueError(
            "O codigo do funcionario nao pode conter os caracteres . # $ [ ] /."
        )


def init_database() -> None:
    _get_firebase_app()


def serialize_embedding(embedding: np.ndarray) -> list[float]:
    return embedding.astype(float).tolist()


def deserialize_embedding(raw_value: list[float] | str) -> np.ndarray:
    if isinstance(raw_value, str):
        raw_sequence = [float(value) for value in raw_value.strip("[]").split(",") if value]
    else:
        raw_sequence = raw_value
    return np.array(raw_sequence, dtype=np.float32)


def get_employee(employee_code: str) -> dict[str, Any] | None:
    _validate_employee_code(employee_code)
    snapshot = _employees_collection().document(employee_code).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()


def employee_exists(employee_code: str) -> bool:
    return get_employee(employee_code) is not None


def create_employee(
    employee_code: str,
    full_name: str,
    department: str | None,
    face_embedding: np.ndarray,
    face_image_base64: str | None,
) -> dict[str, Any]:
    _validate_employee_code(employee_code)
    employee = {
        "id": employee_code,
        "employee_code": employee_code,
        "full_name": full_name,
        "department": department,
        "face_embedding": serialize_embedding(face_embedding),
        "face_image_base64": face_image_base64,
        "presence_state": "outside",
        "last_event_type": None,
        "last_recognized_at": None,
        "created_at": utc_now_iso(),
    }
    _employees_collection().document(employee_code).set(employee)
    return employee


def list_employees() -> list[dict[str, Any]]:
    snapshots = _employees_collection().stream()
    ordered = [snapshot.to_dict() for snapshot in snapshots]
    ordered.sort(key=lambda employee: employee.get("created_at", ""), reverse=True)
    return ordered


def list_employee_embeddings() -> list[dict[str, Any]]:
    employees = list_employees()
    for employee in employees:
        employee["face_embedding"] = deserialize_embedding(employee["face_embedding"])
    return employees


def create_attendance_log(
    employee: dict[str, Any],
    confidence: float,
    event_type: str,
    source: str = "web",
) -> dict[str, Any]:
    employee_code = str(employee["employee_code"])
    current_state = employee.get("presence_state") or "outside"

    if event_type == "entry" and current_state == "inside":
        raise ValueError("Entrada bloqueada: este funcionario ainda nao registrou a saida.")

    if event_type == "exit" and current_state != "inside":
        raise ValueError("Saida bloqueada: este funcionario ainda nao possui uma entrada em aberto.")

    timestamp = utc_now_iso()
    log_reference = _attendance_collection().document()
    attendance_log = {
        "id": log_reference.id,
        "employee_code": employee_code,
        "full_name": employee["full_name"],
        "recognized_at": timestamp,
        "confidence": confidence,
        "source": source,
        "event_type": event_type,
    }
    log_reference.set(attendance_log)

    next_state = "inside" if event_type == "entry" else "outside"
    _employees_collection().document(employee_code).update(
        {
            "presence_state": next_state,
            "last_event_type": event_type,
            "last_recognized_at": timestamp,
        }
    )
    employee.update(
        {
            "presence_state": next_state,
            "last_event_type": event_type,
            "last_recognized_at": timestamp,
        }
    )
    return attendance_log


def list_attendance_logs(limit: int = 100) -> list[dict[str, Any]]:
    query = _attendance_collection().order_by(
        "recognized_at",
        direction=firestore.Query.DESCENDING,
    ).limit(limit)
    return [snapshot.to_dict() for snapshot in query.stream()]


def get_dashboard_metrics() -> dict[str, int]:
    employees = list_employees()
    attendance_logs = list_attendance_logs(limit=10_000)
    return {
        "employees_count": len(employees),
        "attendance_count": len(attendance_logs),
        "present_count": sum(1 for employee in employees if employee.get("presence_state") == "inside"),
    }
