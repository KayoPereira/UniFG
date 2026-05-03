from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
FACES_DIR = Path(os.getenv("FACES_DIR", DATA_DIR / "faces"))
MODELS_DIR = BASE_DIR / "models"


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    faces_dir: Path
    database_path: Path
    firebase_project_id: str | None
    firebase_credentials_path: Path | None
    yunet_model_path: Path
    sface_model_path: Path
    esp8266_url: str | None
    camera_index: int
    face_match_threshold: float
    unknown_streak_frames: int
    known_streak_frames: int
    web_enrollment_samples: int
    web_scan_samples: int


def load_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")

    return Settings(
        base_dir=BASE_DIR,
        data_dir=DATA_DIR,
        faces_dir=FACES_DIR,
        database_path=Path(os.getenv("DATABASE_PATH", DATA_DIR / "attendance.db")),
        firebase_project_id=os.getenv("FIREBASE_PROJECT_ID"),
        firebase_credentials_path=(
            Path(firebase_credentials_path).expanduser()
            if firebase_credentials_path
            else None
        ),
        yunet_model_path=Path(
            os.getenv(
                "YUNET_MODEL_PATH",
                MODELS_DIR / "face_detection_yunet_2023mar.onnx",
            )
        ),
        sface_model_path=Path(
            os.getenv(
                "SFACE_MODEL_PATH",
                MODELS_DIR / "face_recognition_sface_2021dec.onnx",
            )
        ),
        esp8266_url=os.getenv("ESP8266_URL"),
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        face_match_threshold=float(os.getenv("FACE_MATCH_THRESHOLD", "0.363")),
        unknown_streak_frames=int(os.getenv("UNKNOWN_STREAK_FRAMES", "12")),
        known_streak_frames=int(os.getenv("KNOWN_STREAK_FRAMES", "5")),
        web_enrollment_samples=int(os.getenv("WEB_ENROLLMENT_SAMPLES", "5")),
        web_scan_samples=int(os.getenv("WEB_SCAN_SAMPLES", "3")),
    )


settings = load_settings()
