#include <FastLED.h>

#define NUM_LEDS 1
#define DATA_PIN 48 // WS2812 GPIO LED

CRGB leds[NUM_LEDS];

void setup() {

  FastLED.addLeds<NEOPIXEL, DATA_PIN>(leds, NUM_LEDS);
  // pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
}

// the loop function runs over and over again forever
void loop() {
  leds[0] = CRGB::Red; FastLED.show(); delay(1000);
  leds[0] = CRGB::Green; FastLED.show(); delay(1000);
  leds[0] = CRGB::Blue; FastLED.show(); delay(1000);

  // digitalWrite(LED_BUILTIN, HIGH); delay(1000);
  // digitalWrite(LED_BUILTIN, LOW); delay(1000);

  Serial.print("Hola Mundo LED: ");
  Serial.println(LED_BUILTIN);
  delay(1000);
}
