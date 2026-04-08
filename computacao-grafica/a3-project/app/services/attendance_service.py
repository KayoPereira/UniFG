from __future__ import annotations

from pathlib import Path
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
    ) -> dict[str, Any]:
        if employee_exists(employee_code):
            raise ValueError(f"Ja existe um funcionario com o codigo {employee_code}.")

        self.esp_client.send_signal("registering", {"employee_code": employee_code})
        enrollment = self.face_engine.capture_enrollment(self.settings.camera_index)

        photo_path = self.settings.faces_dir / f"{employee_code}.jpg"
        cv2.imwrite(str(photo_path), enrollment.face_crop)

        return create_employee(
            employee_code=employee_code,
            full_name=full_name,
            department=department,
            face_embedding=enrollment.embedding,
            photo_path=photo_path,
        )

    def recognize_and_log(self) -> RecognitionResult:
        employees = list_employee_embeddings()
        if not employees:
            raise RuntimeError("Nenhum funcionario cadastrado. Faca pelo menos um cadastro antes do reconhecimento.")

        result = self.face_engine.recognize(self.settings.camera_index, employees)

        if result.status == "recognized" and result.employee is not None:
            create_attendance_log(
                employee_id=int(result.employee["id"]),
                confidence=result.confidence,
            )
            self.esp_client.send_signal(
                "recognized",
                {
                    "employee_code": result.employee["employee_code"],
                    "confidence": f"{result.confidence:.3f}",
                },
            )
        else:
            self.esp_client.send_signal("unknown")

        return result
