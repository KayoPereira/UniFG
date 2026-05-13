from __future__ import annotations

import base64
from typing import Any

import cv2

from ..config import settings
from ..database import (
    create_resident,
    resident_exists,
    init_database,
    # list_resident_embeddings,  # Supondo que será implementado
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
        # Implementação futura: lógica de reconhecimento e registro de acesso
        raise NotImplementedError("Função de reconhecimento ainda não implementada.")
