#include <Wire.h>
#include <Adafruit_VL53L0X.h>

Adafruit_VL53L0X lox = Adafruit_VL53L0X();

void setup() {
  Serial.begin(9600);
  if (!lox.begin()) {
    Serial.println("No se encontró VL53L0X");
    while(1);
  }
}

void loop() {
  VL53L0X_RangingMeasurementData_t measure;
  lox.rangingTest(&measure, false);
  
  if (measure.RangeStatus != 4) { 
    Serial.print("Distancia (mm): "); 
    Serial.println(measure.RangeMilliMeter);
  } else {
    Serial.println("Fuera de rango");
  }
  delay(100);
}
