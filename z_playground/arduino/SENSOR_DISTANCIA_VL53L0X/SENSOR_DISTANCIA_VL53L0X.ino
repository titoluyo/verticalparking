#include <Wire.h>
#include <Adafruit_VL53L0X.h>

Adafruit_VL53L0X lox = Adafruit_VL53L0X();

float correctionFactor = 0.99; // Factor de corrección para ajustar la medición

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
    // Aplicar el factor de corrección a la medición
    float correctedDistance = measure.RangeMilliMeter * correctionFactor;
    
    Serial.print("Distancia corregida (mm): "); 
    Serial.println(correctedDistance);
  } else {
    Serial.println("Fuera de rango");
  }
  delay(100);
}
