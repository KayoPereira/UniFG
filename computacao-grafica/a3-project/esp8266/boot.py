import network
import time


WIFI_SSID = "SEU_WIFI"
WIFI_PASSWORD = "SUA_SENHA"


def connect_wifi() -> None:
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("Wi-Fi ja conectado:", wlan.ifconfig())
        return

    print("Conectando ao Wi-Fi...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    for _ in range(20):
        if wlan.isconnected():
            print("Wi-Fi conectado:", wlan.ifconfig())
            return
        time.sleep(1)

    print("Falha ao conectar no Wi-Fi")


connect_wifi()
