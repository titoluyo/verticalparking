# sensors.py
import time, board, busio, digitalio, adafruit_vl53l0x, config

class Sensors:
    def __init__(self, use_s3=True, use_c6=False):
        # IR inputs on IO2 / IO3
        self._ir1 = digitalio.DigitalInOut(board.IO2)
        self._ir1.direction = digitalio.Direction.INPUT
        self._ir2 = digitalio.DigitalInOut(board.IO3)
        self._ir2.direction = digitalio.Direction.INPUT
        if config.IR_PULLUPS:
            self._ir1.pull = digitalio.Pull.UP
            self._ir2.pull = digitalio.Pull.UP

        # I2C
        if use_c6:
            i2c = busio.I2C(scl=board.IO15, sda=board.IO14)   # ESP32-C6
        else:
            i2c = busio.I2C(scl=board.IO9, sda=board.IO8)     # ESP32-S3
        self._vl53 = adafruit_vl53l0x.VL53L0X(i2c)

        # state for edge detection
        self._last_ir1 = None
        self._last_ir2 = None
        self._last_dist = None

    def read(self):
        # If using pull-ups: active-low → occupied when value==False
        occ1 = (not self._ir1.value) if config.IR_PULLUPS else bool(self._ir1.value)
        occ2 = (not self._ir2.value) if config.IR_PULLUPS else bool(self._ir2.value)
        dist = int(self._vl53.range)
        return occ1, occ2, dist

    def telemetry(self):
        occ1, occ2, dist = self.read()
        return {"ir1": occ1, "ir2": occ2, "distance_mm": dist}

    def edge_events(self, dist_threshold=20):
        events = []
        occ1, occ2, dist = self.read()

        print(f"IR1: {self._last_ir1}|{occ1}; # IR2: {self._last_ir2}|{occ2}; # Distance: {self._last_dist}|{dist}")

        if self._last_ir1 is None or occ1 != self._last_ir1:
            events.append({"type": "ir1", "value": occ1})
            print(f"  IR1 state changed to {occ1}")
            self._last_ir1 = occ1

        if self._last_ir2 is None or occ2 != self._last_ir2:
            events.append({"type": "ir2", "value": occ2})
            print(f"  IR2 state changed to {occ2}")
            self._last_ir2 = occ2

        if self._last_dist is None:
            self._last_dist = dist
        else:
            if abs(dist - self._last_dist) >= dist_threshold:
                events.append({"type": "distance_change", "from": self._last_dist, "to": dist})
                print(f"  Distance changed from {self._last_dist}mm to {dist}mm")
                self._last_dist = dist

        return events
