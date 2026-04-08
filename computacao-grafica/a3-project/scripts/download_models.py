from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen


BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"

MODEL_URLS = {
    "face_detection_yunet_2023mar.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def download_file(filename: str, url: str) -> None:
    destination = MODELS_DIR / filename
    if destination.exists():
        print(f"Modelo ja existe: {destination}")
        return

    print(f"Baixando {filename}...")
    with urlopen(url) as response:
        destination.write_bytes(response.read())
    print(f"Modelo salvo em: {destination}")


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in MODEL_URLS.items():
        download_file(filename, url)


if __name__ == "__main__":
    main()
