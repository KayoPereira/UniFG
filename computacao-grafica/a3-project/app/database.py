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


def _residents_collection():
    return _get_firestore_client().collection("residents")

def _access_collection():
    return _get_firestore_client().collection("access_logs")




def _validate_resident_code(resident_code: str) -> None:
    invalid_chars = ".#$[]/"
    if any(char in resident_code for char in invalid_chars):
        raise ValueError(
            "O código do morador/visitante não pode conter os caracteres . # $ [ ] /."
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




def get_resident(resident_code: str) -> dict[str, Any] | None:
    _validate_resident_code(resident_code)
    snapshot = _residents_collection().document(resident_code).get()
    if not snapshot.exists:
        return None
    return snapshot.to_dict()




def resident_exists(resident_code: str) -> bool:
    return get_resident(resident_code) is not None




def create_resident(
    resident_code: str,
    full_name: str,
    unit: str | None,
    face_embedding: np.ndarray,
    face_image_base64: str | None,
) -> dict[str, Any]:
    _validate_resident_code(resident_code)
    resident = {
        "id": resident_code,
        "resident_code": resident_code,
        "full_name": full_name,
        "unit": unit,
        "face_embedding": serialize_embedding(face_embedding),
        "face_image_base64": face_image_base64,
        "presence_state": "outside",
        "last_event_type": None,
        "last_recognized_at": None,
        "created_at": utc_now_iso(),
    }
    _residents_collection().document(resident_code).set(resident)
    return resident




def list_residents() -> list[dict[str, Any]]:
    return [doc.to_dict() for doc in _residents_collection().stream()]


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
        raise ValueError("Entrada bloqueada: este morador/visitante ainda não registrou a saída.")

    if event_type == "exit" and current_state != "inside":
        raise ValueError("Saída bloqueada: este morador/visitante ainda não possui uma entrada em aberto.")

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


def get_dashboard_metrics() -> dict[str, Any]:
    residents = list_residents()
    logs = _access_collection().stream() if hasattr(_access_collection(), 'stream') else []
    return {
        "residents_count": len(residents),
        "attendance_count": sum(1 for _ in logs),
        "present_count": sum(1 for r in residents if r.get("presence_state") == "inside"),
    }
