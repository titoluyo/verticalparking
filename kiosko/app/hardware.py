"""
Optional Raspberry Pi hardware integration.
If running on Linux and gpiozero is available, toggles GPIO17 LED.
Falls back to simulation print on other platforms or missing deps.
"""
import platform
import time


def _is_raspberry_linux() -> bool:
    return platform.system() == "Linux"


def activar_led_ok() -> None:
    """Turn on LED on GPIO 17 for 2 seconds (if available)."""
    if not _is_raspberry_linux():
        print("Simulación LED encendido")
        return

    try:
        from gpiozero import LED  # type: ignore

        led = LED(17)
        led.on()
        time.sleep(2)
        led.off()
    except Exception as exc:  # ImportError or runtime errors
        print(f"Simulación LED encendido (fallback). Detalle: {exc}")

