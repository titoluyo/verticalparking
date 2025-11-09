import time
import board
import busio
import digitalio

import adafruit_vl53l0x

ir_sensor_pin1 = digitalio.DigitalInOut(board.IO2)
ir_sensor_pin1.direction = digitalio.Direction.INPUT
ir_sensor_pin2 = digitalio.DigitalInOut(board.IO3)
ir_sensor_pin2.direction = digitalio.Direction.INPUT

time.sleep(0.1)

i2c = busio.I2C(scl=board.IO15, sda=board.IO14)
#i2c = busio.I2C(scl=board.IO9, sda=board.IO8) 
vl53 = adafruit_vl53l0x.VL53L0X(i2c)

while True:
    print(f"Range: {vl53.range}mm - {'Ocupado' if ir_sensor_pin1.value else 'Libre'} - {'Ocupado' if ir_sensor_pin2.value else 'Libre'}")
    time.sleep(0.1)

