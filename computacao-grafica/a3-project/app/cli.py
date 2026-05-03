from __future__ import annotations

import argparse
import logging

from .database import init_database
from .web import create_app


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sistema de ponto com reconhecimento facial via navegador e integracao com ESP8266.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Valida a conexao configurada com o Firebase.")

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
        print("Firebase validado com sucesso.")
        return

    if args.command == "serve":
        app = create_app()
        app.run(host=args.host, port=args.port, debug=args.debug)
        return


if __name__ == "__main__":
    main()
