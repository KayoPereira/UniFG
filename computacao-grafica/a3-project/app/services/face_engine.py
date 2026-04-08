from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..config import Settings


@dataclass
class EnrollmentResult:
    embedding: np.ndarray
    face_crop: np.ndarray


@dataclass
class RecognitionResult:
    status: str
    confidence: float
    employee: dict | None
    frame: np.ndarray | None


class FaceEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ensure_models_exist()
        self.detector = self._create_detector()
        self.recognizer = self._create_recognizer()

    def _ensure_models_exist(self) -> None:
        missing_files = [
            path
            for path in (
                self.settings.yunet_model_path,
                self.settings.sface_model_path,
            )
            if not Path(path).exists()
        ]
        if missing_files:
            missing = ", ".join(str(path) for path in missing_files)
            raise FileNotFoundError(
                f"Modelos ONNX ausentes: {missing}. Execute 'python -m scripts.download_models'."
            )

    def _create_detector(self):
        if hasattr(cv2, "FaceDetectorYN_create"):
            return cv2.FaceDetectorYN_create(
                str(self.settings.yunet_model_path),
                "",
                (320, 320),
                0.85,
                0.3,
                5000,
            )

        return cv2.FaceDetectorYN.create(
            str(self.settings.yunet_model_path),
            "",
            (320, 320),
            score_threshold=0.85,
            nms_threshold=0.3,
            top_k=5000,
        )

    def _create_recognizer(self):
        if hasattr(cv2, "FaceRecognizerSF_create"):
            return cv2.FaceRecognizerSF_create(
                str(self.settings.sface_model_path),
                "",
            )

        return cv2.FaceRecognizerSF.create(
            str(self.settings.sface_model_path),
            "",
        )

    def _detect_primary_face(self, frame: np.ndarray) -> np.ndarray | None:
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame)

        if faces is None or len(faces) == 0:
            return None

        return max(faces, key=lambda candidate: candidate[2] * candidate[3])

    def _extract_features(self, frame: np.ndarray, face: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        aligned_face = self.recognizer.alignCrop(frame, face)
        embedding = self.recognizer.feature(aligned_face)
        normalized = embedding.flatten().astype(np.float32)
        normalized /= np.linalg.norm(normalized)
        return normalized, aligned_face

    def _match_embeddings(self, probe_embedding: np.ndarray, reference_embedding: np.ndarray) -> float:
        probe = probe_embedding.reshape(1, -1)
        reference = reference_embedding.reshape(1, -1)
        return float(
            self.recognizer.match(
                probe,
                reference,
                cv2.FaceRecognizerSF_FR_COSINE,
            )
        )

    def _draw_overlay(self, frame: np.ndarray, label: str, color: tuple[int, int, int]) -> None:
        cv2.rectangle(frame, (16, 16), (620, 84), (15, 18, 28), -1)
        cv2.putText(
            frame,
            label,
            (28, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            color,
            2,
            cv2.LINE_AA,
        )

    def list_available_cameras(self, max_index: int = 6) -> list[int]:
        available_indexes: list[int] = []

        for camera_index in range(max_index + 1):
            capture = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(camera_index)

            if capture.isOpened():
                ok, _ = capture.read()
                if ok:
                    available_indexes.append(camera_index)

            capture.release()

        return available_indexes

    def _open_camera(self, camera_index: int) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
        if capture.isOpened():
            return capture

        capture.release()
        capture = cv2.VideoCapture(camera_index)
        if capture.isOpened():
            return capture

        available_indexes = self.list_available_cameras()
        if available_indexes:
            available_text = ", ".join(str(index) for index in available_indexes)
            raise RuntimeError(
                "Nao foi possivel abrir a webcam no indice "
                f"{camera_index}. Cameras disponiveis detectadas: {available_text}. "
                "Defina CAMERA_INDEX com um desses valores."
            )

        raise RuntimeError(
            "Nao foi possivel abrir a webcam e nenhuma camera foi detectada pelo OpenCV. "
            "No Linux, confirme se a webcam aparece em /dev/video0, se nao esta em uso por outro programa "
            "e se o sistema tem permissao para acessa-la."
        )

    def capture_enrollment(self, camera_index: int, samples_required: int = 7) -> EnrollmentResult:
        capture = self._open_camera(camera_index)

        collected_embeddings: list[np.ndarray] = []
        last_crop: np.ndarray | None = None

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Falha ao capturar imagem da webcam.")

                face = self._detect_primary_face(frame)
                preview = frame.copy()

                if face is not None:
                    x, y, width, height = face[:4].astype(int)
                    cv2.rectangle(preview, (x, y), (x + width, y + height), (0, 200, 255), 2)
                    message = (
                        f"Cadastro: pressione C para coletar amostra {len(collected_embeddings) + 1}/{samples_required}"
                    )
                    self._draw_overlay(preview, message, (0, 220, 255))
                else:
                    self._draw_overlay(
                        preview,
                        "Cadastro: posicione apenas um rosto na camera e pressione C",
                        (60, 60, 255),
                    )

                cv2.imshow("Cadastro Facial", preview)
                pressed_key = cv2.waitKey(1) & 0xFF

                if pressed_key == ord("q"):
                    raise RuntimeError("Cadastro cancelado pelo usuario.")

                if pressed_key == ord("c"):
                    if face is None:
                        continue

                    embedding, last_crop = self._extract_features(frame, face)
                    collected_embeddings.append(embedding)

                    if len(collected_embeddings) >= samples_required:
                        average_embedding = np.mean(collected_embeddings, axis=0)
                        average_embedding /= np.linalg.norm(average_embedding)
                        if last_crop is None:
                            raise RuntimeError("Nao foi possivel capturar uma foto de referencia.")
                        return EnrollmentResult(
                            embedding=average_embedding.astype(np.float32),
                            face_crop=last_crop,
                        )
        finally:
            capture.release()
            cv2.destroyAllWindows()

    def recognize(self, camera_index: int, employees: list[dict]) -> RecognitionResult:
        capture = self._open_camera(camera_index)

        known_streak = 0
        unknown_streak = 0
        previous_employee_code: str | None = None

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Falha ao capturar imagem da webcam.")

                preview = frame.copy()
                face = self._detect_primary_face(frame)

                if face is None:
                    known_streak = 0
                    unknown_streak = 0
                    previous_employee_code = None
                    self._draw_overlay(preview, "Reconhecimento: aproxime um rosto da camera", (255, 255, 255))
                    cv2.imshow("Reconhecimento Facial", preview)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        raise RuntimeError("Reconhecimento cancelado pelo usuario.")
                    continue

                x, y, width, height = face[:4].astype(int)
                cv2.rectangle(preview, (x, y), (x + width, y + height), (94, 255, 140), 2)
                embedding, _ = self._extract_features(frame, face)

                best_employee = None
                best_score = -1.0

                for employee in employees:
                    score = self._match_embeddings(embedding, employee["face_embedding"])
                    if score > best_score:
                        best_score = score
                        best_employee = employee

                if best_employee and best_score >= self.settings.face_match_threshold:
                    current_code = str(best_employee["employee_code"])
                    known_streak = known_streak + 1 if previous_employee_code == current_code else 1
                    unknown_streak = 0
                    previous_employee_code = current_code
                    self._draw_overlay(
                        preview,
                        f"Reconhecido: {best_employee['full_name']} | similaridade {best_score:.3f}",
                        (94, 255, 140),
                    )

                    if known_streak >= self.settings.known_streak_frames:
                        return RecognitionResult(
                            status="recognized",
                            confidence=best_score,
                            employee=best_employee,
                            frame=frame,
                        )
                else:
                    known_streak = 0
                    previous_employee_code = None
                    unknown_streak += 1
                    self._draw_overlay(
                        preview,
                        f"Desconhecido | similaridade maxima {best_score:.3f}",
                        (60, 60, 255),
                    )

                    if unknown_streak >= self.settings.unknown_streak_frames:
                        return RecognitionResult(
                            status="unknown",
                            confidence=max(best_score, 0.0),
                            employee=None,
                            frame=frame,
                        )

                cv2.imshow("Reconhecimento Facial", preview)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    raise RuntimeError("Reconhecimento cancelado pelo usuario.")
        finally:
            capture.release()
            cv2.destroyAllWindows()
