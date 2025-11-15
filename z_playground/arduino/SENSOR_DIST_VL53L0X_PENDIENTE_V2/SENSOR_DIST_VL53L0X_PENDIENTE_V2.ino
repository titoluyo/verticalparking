#include <Wire.h>
#include <Adafruit_VL53L0X.h>

Adafruit_VL53L0X lox = Adafruit_VL53L0X();

float slope = 0.9071;  // Pendiente de la ecuación lineal
float intercept = 40;  // Intersección de la ecuación lineal

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
    // Aplicar la corrección usando la ecuación: distancia real = (medido - intercept) / slope
    float realDistance = (measure.RangeMilliMeter - intercept) / slope;
    
    Serial.print("Distancia corregida (mm): "); 
    Serial.println(realDistance);
  } else {
    Serial.println("Fuera de rango");
  }
  delay(100);
}