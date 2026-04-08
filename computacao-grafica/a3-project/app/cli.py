from __future__ import annotations

import argparse
import logging

from .config import settings
from .database import init_database
from .services.face_engine import FaceEngine
from .services.attendance_service import AttendanceService
from .web import create_app


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sistema de ponto com reconhecimento facial e integracao com ESP8266.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Inicializa o banco de dados SQLite.")

    enroll_parser = subparsers.add_parser("enroll", help="Cadastra um novo funcionario.")
    enroll_parser.add_argument("--code", required=True, help="Codigo unico do funcionario.")
    enroll_parser.add_argument("--name", required=True, help="Nome completo do funcionario.")
    enroll_parser.add_argument("--department", help="Departamento do funcionario.")

    subparsers.add_parser("recognize", help="Reconhece um rosto e registra o ponto.")

    cameras_parser = subparsers.add_parser(
        "list-cameras",
        help="Lista indices de camera que o OpenCV consegue abrir.",
    )
    cameras_parser.add_argument(
        "--max-index",
        type=int,
        default=6,
        help="Maior indice a testar ao procurar cameras.",
    )

    serve_parser = subparsers.add_parser("serve", help="Inicia o mini-site em Flask.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--debug", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        init_database()
        print("Banco de dados inicializado com sucesso.")
        return

    if args.command == "serve":
        app = create_app()
        app.run(host=args.host, port=args.port, debug=args.debug)
        return

    if args.command == "list-cameras":
        face_engine = FaceEngine(settings)
        cameras = face_engine.list_available_cameras(args.max_index)
        if cameras:
            print("Cameras detectadas:", ", ".join(str(index) for index in cameras))
        else:
            print("Nenhuma camera foi detectada pelo OpenCV.")
        return

    service = AttendanceService()

    if args.command == "enroll":
        employee = service.register_employee(
            employee_code=args.code,
            full_name=args.name,
            department=args.department,
        )
        print(
            f"Funcionario cadastrado: {employee['full_name']} ({employee['employee_code']})"
        )
        return

    if args.command == "recognize":
        result = service.recognize_and_log()
        if result.status == "recognized" and result.employee is not None:
            print(
                "Ponto registrado para "
                f"{result.employee['full_name']} "
                f"({result.employee['employee_code']}) "
                f"com similaridade {result.confidence:.3f}."
            )
        else:
            print("Rosto nao cadastrado identificado. Sinal de desconhecido enviado ao ESP8266.")


if __name__ == "__main__":
    main()
