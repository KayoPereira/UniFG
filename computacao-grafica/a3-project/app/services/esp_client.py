from __future__ import annotations

import logging
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)


class ESP8266Client:
    def __init__(self, base_url: str | None) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None

    def send_signal(self, state: str, payload: dict[str, Any] | None = None) -> bool:
        if not self.base_url:
            LOGGER.info("ESP8266_URL nao configurada; sinal '%s' nao enviado.", state)
            return False

        params = {"state": state}
        if payload:
            params.update(payload)

        try:
            response = requests.get(
                f"{self.base_url}/signal",
                params=params,
                timeout=2,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            LOGGER.warning("Falha ao enviar sinal '%s' para o ESP8266: %s", state, exc)
            return False
