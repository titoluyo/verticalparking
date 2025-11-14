// #include <FastLED.h>

#define NUM_LEDS 1
#define DATA_PIN 8 // WS2812 GPIO LED for ESP32-C6 Super Mini

// CRGB leds[NUM_LEDS];

void setup() {
//  FastLED.addLeds<NEOPIXEL, DATA_PIN>(leds, NUM_LEDS);
  Serial.begin(115200); // Higher baud rate for ESP32-C6
}

// the loop function runs over and over again forever
void loop() {
//  leds[0] = CRGB::Red; FastLED.show(); delay(1000);
//  leds[0] = CRGB::Green; FastLED.show(); delay(1000);
//  leds[0] = CRGB::Blue; FastLED.show(); delay(1000);

  Serial.print("Hola Mundo LED ESP32-C6: ");
  Serial.println(DATA_PIN);
  delay(1000);
}