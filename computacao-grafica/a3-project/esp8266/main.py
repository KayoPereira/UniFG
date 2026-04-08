import socket
import time
from machine import Pin


LED = Pin(2, Pin.OUT)


def led_on() -> None:
    LED.value(0)


def led_off() -> None:
    LED.value(1)


def blink(times: int, on_time: float, off_time: float) -> None:
    for _ in range(times):
        led_on()
        time.sleep(on_time)
        led_off()
        time.sleep(off_time)


def handle_state(state: str) -> None:
    print("Sinal recebido:", state)

    if state == "recognized":
        led_on()
        time.sleep(2)
        led_off()
        return

    if state == "unknown":
        blink(3, 0.15, 0.15)
        return

    if state == "registering":
        blink(5, 0.4, 0.2)
        return

    blink(2, 0.05, 0.05)


def parse_state(request_text: str) -> str:
    try:
        first_line = request_text.split("\r\n", 1)[0]
        path = first_line.split(" ")[1]
        if "?" not in path:
            return ""
        query = path.split("?", 1)[1]
        for item in query.split("&"):
            if item.startswith("state="):
                return item.split("=", 1)[1]
    except Exception as exc:
        print("Falha ao interpretar request:", exc)
    return ""


def serve() -> None:
    address = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    server = socket.socket()
    server.bind(address)
    server.listen(1)
    print("Servidor HTTP aguardando em", address)

    led_off()

    while True:
        client, client_address = server.accept()
        print("Cliente conectado:", client_address)
        try:
            request_text = client.recv(1024).decode()
            state = parse_state(request_text)
            if state:
                handle_state(state)
                body = '{"status":"ok","state":"%s"}' % state
            else:
                body = '{"status":"error","message":"missing state"}'

            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                "Connection: close\r\n\r\n"
                + body
            )
            client.send(response)
        finally:
            client.close()


serve()