#include <Wire.h>
#include <Adafruit_VL53L0X.h>

Adafruit_VL53L0X lox = Adafruit_VL53L0X();

int sensorPin = 2;    // OUT del sensor de proximidad IR al pin D2
int ledPin = 13;      // LED integrado en el Nano
int valorSensor = 0;

float slope = 0.9071;  // Pendiente de la ecuación lineal
float intercept = 40;  // Intersección de la ecuación lineal

void setup() {
  pinMode(sensorPin, INPUT);
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
  Serial.println("PRUEBAS DE SENSOR IR - PRESENCIA");
  Serial.println("PRUEBAS DE SENSOR DE POSICIONAMIENTO VERTICAL");
  delay(1000);

  // Inicialización del sensor de distancia
  if (!lox.begin()) {
    Serial.println("No se encontró VL53L0X");
    while(1);
  }
  // Cambiar la dirección del sensor para evitar conflicto 
  //lox.setAddress(0x30);  // Cambiar la dirección a 0x30
}

void loop() {
  // Sensor de proximidad IR
  valorSensor = digitalRead(sensorPin);

  if (valorSensor == LOW) { 
    // Algunos sensores dan LOW cuando detectan obstáculo
    digitalWrite(ledPin, HIGH);
    Serial.println("Ocupado!");
  } else {
    digitalWrite(ledPin, LOW);
    Serial.println("Libre");
  }

  // Sensor de distancia (VL53L0X)
  VL53L0X_RangingMeasurementData_t measure;
  lox.rangingTest(&measure, false);

  if (measure.RangeStatus != 4) { 
    // Aplicar la corrección usando la ecuación: distancia real = (medido - intercept) / slope
    float realDistance = (measure.RangeMilliMeter - intercept) / slope;
    Serial.print("Altura: "); 
    Serial.println(realDistance);
  } else {
    Serial.println("Fuera de rango");
  }

  delay(1000); // Espera entre lecturas
}
