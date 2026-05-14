from __future__ import annotations

import base64
from typing import Any

import cv2

from ..config import settings
from ..database import (
    create_access_log,
    create_resident,
    deserialize_embedding,
    init_database,
    list_residents,
    resident_exists,
)
from .esp_client import ESP8266Client
from .face_engine import FaceEngine, RecognitionResult


class AccessService:
    def __init__(self) -> None:
        init_database()
        self.settings = settings
        self.face_engine = FaceEngine(settings)
        self.esp_client = ESP8266Client(settings.esp8266_url)

    def register_resident(
        self,
        resident_code: str,
        full_name: str,
        unit: str | None,
        images: list[bytes],
    ) -> dict[str, Any]:
        if not resident_code:
            raise ValueError("Informe um código para o morador/visitante.")

        if not full_name:
            raise ValueError("Informe o nome completo do morador/visitante.")

        if resident_exists(resident_code):
            raise ValueError(f"Já existe um morador/visitante com o código {resident_code}.")

        self.esp_client.send_signal("registering", {"resident_code": resident_code})
        enrollment = self.face_engine.create_enrollment_from_images(images)

        encoded_ok, encoded_face = cv2.imencode(".jpg", enrollment.face_crop)
        if not encoded_ok:
            raise RuntimeError("Não foi possível gerar a foto facial do cadastro.")

        return create_resident(
            resident_code=resident_code,
            full_name=full_name,
            unit=unit,
            face_embedding=enrollment.embedding,
            face_image_base64=base64.b64encode(encoded_face.tobytes()).decode("ascii"),
        )

    def recognize_and_log(
        self,
        images: list[bytes],
        event_type: str,
        source: str = "web",
    ) -> dict[str, Any]:
        residents = list_residents()
        if not residents:
            return {"status": "unknown", "message": "Nenhum morador/visitante cadastrado no sistema."}

        for resident in residents:
            resident["face_embedding"] = deserialize_embedding(resident["face_embedding"])

        result = self.face_engine.recognize_from_images(images, residents)

        if result.status != "recognized" or result.employee is None:
            return {"status": "unknown", "message": "Rosto não reconhecido. Acesso negado."}

        matched_resident = result.employee
        log = create_access_log(
            resident=matched_resident,
            confidence=result.confidence,
            event_type=event_type,
            source=source,
        )

        self.esp_client.send_signal(event_type, {"resident_code": matched_resident["resident_code"]})

        return {
            "status": "success",
            "message": f"{matched_resident['full_name']} — {event_type} registrado com sucesso.",
            "log": log,
        }
