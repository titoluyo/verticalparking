# net.py
import wifi, socketpool, config

def connect_wifi():
    print("Connecting Wi-Fi...")
    wifi.radio.connect(config.SSID, config.PWD)
    print("Wi-Fi OK, IP:", wifi.radio.ipv4_address)
    return wifi.radio

def socket_pool():
    return socketpool.SocketPool(wifi.radio)
