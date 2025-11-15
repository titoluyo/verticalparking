int sensorPin = 2;    // OUT del sensor al pin D2
int ledPin = 13;      // LED integrado en el Nano
int valorSensor = 0;

void setup() {
  pinMode(sensorPin, INPUT);
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  valorSensor = digitalRead(sensorPin);

  if (valorSensor == LOW) { 
    // Algunos sensores dan LOW cuando detectan obstáculo
    digitalWrite(ledPin, HIGH);
    Serial.println("Obstaculo detectado!");
  } else {
    digitalWrite(ledPin, LOW);
    Serial.println("Libre");
  }

  delay(200);
}
