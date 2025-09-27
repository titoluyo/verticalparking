#include <Arduino.h>

#define LED_PIN 47

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  Serial.println("ESP32-S3 Supermini Blink Started!");
  Serial.print("LED Pin: ");
  Serial.println(LED_PIN);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  Serial.println("LED ON");
  delay(1000);

  digitalWrite(LED_PIN, LOW);
  Serial.println("LED OFF");
  delay(1000);
}