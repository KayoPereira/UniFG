from __future__ import annotations

import base64
from typing import Any

import cv2

from ..config import settings
from ..database import (
    create_attendance_log,
    create_employee,
    employee_exists,
    init_database,
    list_employee_embeddings,
)
from .esp_client import ESP8266Client
from .face_engine import FaceEngine, RecognitionResult


class AttendanceService:
    def __init__(self) -> None:
        init_database()
        self.settings = settings
        self.face_engine = FaceEngine(settings)
        self.esp_client = ESP8266Client(settings.esp8266_url)

    def register_employee(
        self,
        employee_code: str,
        full_name: str,
        department: str | None,
        images: list[bytes],
    ) -> dict[str, Any]:
        if not employee_code:
            raise ValueError("Informe um codigo para o funcionario.")

        if not full_name:
            raise ValueError("Informe o nome completo do funcionario.")

        if employee_exists(employee_code):
            raise ValueError(f"Ja existe um funcionario com o codigo {employee_code}.")

        self.esp_client.send_signal("registering", {"employee_code": employee_code})
        enrollment = self.face_engine.create_enrollment_from_images(images)

        encoded_ok, encoded_face = cv2.imencode(".jpg", enrollment.face_crop)
        if not encoded_ok:
            raise RuntimeError("Nao foi possivel gerar a foto facial do cadastro.")

        return create_employee(
            employee_code=employee_code,
            full_name=full_name,
            department=department,
            face_embedding=enrollment.embedding,
            face_image_base64=base64.b64encode(encoded_face.tobytes()).decode("ascii"),
        )

    def recognize_and_log(
        self,
        images: list[bytes],
        event_type: str,
        source: str = "web",
    ) -> dict[str, Any]:
        employees = list_employee_embeddings()
        if not employees:
            raise RuntimeError("Nenhum funcionario cadastrado. Faca pelo menos um cadastro antes do reconhecimento.")

        result = self.face_engine.recognize_from_images(images, employees)

        if result.status == "recognized" and result.employee is not None:
            try:
                attendance_log = create_attendance_log(
                    employee=result.employee,
                    confidence=result.confidence,
                    event_type=event_type,
                    source=source,
                )
            except ValueError:
                self.esp_client.send_signal(
                    "denied",
                    {
                        "employee_code": result.employee["employee_code"],
                        "event_type": event_type,
                    },
                )
                raise

            self.esp_client.send_signal(
                "recognized",
                {
                    "employee_code": result.employee["employee_code"],
                    "event_type": event_type,
                    "confidence": f"{result.confidence:.3f}",
                },
            )
            return {
                "status": "success",
                "confidence": result.confidence,
                "employee": {
                    "employee_code": result.employee["employee_code"],
                    "full_name": result.employee["full_name"],
                },
                "attendance": attendance_log,
                "message": (
                    f"{result.employee['full_name']} teve a {event_type} registrada com sucesso."
                ),
            }

        else:
            self.esp_client.send_signal("unknown")

        return {
            "status": "unknown",
            "confidence": result.confidence,
            "employee": None,
            "attendance": None,
            "message": "Nenhum rosto cadastrado foi reconhecido nas capturas enviadas.",
        }
