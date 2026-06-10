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

_LIVENESS_TILT_THRESHOLD = 15.0  # degrees — any tilt beyond this passes


class LivenessCheckError(ValueError):
    """Raised when the liveness head-tilt check fails.

    The `angle` attribute carries the last detected tilt angle (or None if no
    face was found), so the API can relay it to the frontend for live dot feedback.
    """

    def __init__(self, message: str, angle: float | None = None) -> None:
        super().__init__(message)
        self.angle = angle


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

    def scan_for_recognition(
        self,
        images: list[bytes],
        event_type: str,
    ) -> dict[str, Any]:
        """Phase 1: recognize the face and return a liveness challenge.
        Does NOT log any attendance event.
        """
        employees = list_employee_embeddings()
        if not employees:
            raise RuntimeError(
                "Nenhum funcionario cadastrado. Faca pelo menos um cadastro antes do reconhecimento."
            )

        result = self.face_engine.recognize_from_images(images, employees)

        if result.status != "recognized" or result.employee is None:
            self.esp_client.send_signal("unknown")
            return {"status": "unknown", "confidence": result.confidence}

        employee = result.employee

        # Early state check — gives immediate feedback before liveness
        state = employee.get("presence_state", "outside")
        if event_type == "entry" and state == "inside":
            self.esp_client.send_signal("denied", {"employee_code": employee["employee_code"]})
            raise ValueError("Entrada bloqueada: este funcionario ainda nao registrou a saida.")
        if event_type == "exit" and state != "inside":
            self.esp_client.send_signal("denied", {"employee_code": employee["employee_code"]})
            raise ValueError("Saida bloqueada: este funcionario ainda nao possui uma entrada em aberto.")

        return {
            "status": "recognized",
            "confidence": result.confidence,
            "employee": {
                "employee_code": employee["employee_code"],
                "full_name": employee["full_name"],
            },
        }

    def confirm_with_liveness(
        self,
        images: list[bytes],
        employee_code: str,
        event_type: str,
        confidence: float,
    ) -> dict[str, Any]:
        """Phase 2: verify head-tilt liveness (any direction) and log the attendance event.

        The detected angle is attached to LivenessCheckError so the API can
        return it to the frontend, which uses it to pulse the correct dot cluster.
        """
        detected_angle: float | None = None
        tilt_passed = False

        for img in images:
            angle = self.face_engine.estimate_head_tilt(img)
            if angle is not None:
                detected_angle = angle
                if abs(angle) > _LIVENESS_TILT_THRESHOLD:
                    tilt_passed = True
                    break

        if not tilt_passed:
            raise LivenessCheckError(
                "Incline a cabeca para qualquer lado para confirmar sua presenca.",
                angle=detected_angle,
            )

        employees = list_employee_embeddings()
        employee = next(
            (e for e in employees if str(e["employee_code"]) == str(employee_code)),
            None,
        )
        if employee is None:
            raise RuntimeError("Funcionario nao encontrado na base de dados.")

        attendance_log = create_attendance_log(
            employee=employee,
            confidence=confidence,
            event_type=event_type,
            source="web",
        )
        self.esp_client.send_signal(
            "recognized",
            {
                "employee_code": employee_code,
                "event_type": event_type,
                "confidence": f"{confidence:.3f}",
            },
        )
        event_label = "entrada" if event_type == "entry" else "saida"
        return {
            "status": "success",
            "message": f"{employee['full_name']} teve a {event_label} registrada com sucesso.",
            "attendance": attendance_log,
            "employee": {
                "employee_code": employee_code,
                "full_name": employee["full_name"],
            },
        }

    def get_head_tilt_angle(self, images: list[bytes]) -> float | None:
        """Return the first detected head tilt angle. Used for real-time visual feedback."""
        for img in images:
            angle = self.face_engine.estimate_head_tilt(img)
            if angle is not None:
                return angle
        return None

    # Legacy method kept for reference — no longer used by the web routes
    def recognize_and_log(
        self,
        images: list[bytes],
        event_type: str,
        source: str = "web",
    ) -> dict[str, Any]:
        employees = list_employee_embeddings()
        if not employees:
            raise RuntimeError("Nenhum funcionario cadastrado.")

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
                    {"employee_code": result.employee["employee_code"], "event_type": event_type},
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

        self.esp_client.send_signal("unknown")
        return {
            "status": "unknown",
            "confidence": result.confidence,
            "employee": None,
            "attendance": None,
            "message": "Nenhum rosto cadastrado foi reconhecido nas capturas enviadas.",
        }
