#include <Arduino.h>
#include <FastLED.h>

#define PIXEL_PIN 48
#define NUM_PIXELS 1
#define LED_BRIGHTNESS 32
#define COLOR_SWITCH_DELAY_MS 1000

static CRGB pixels[NUM_PIXELS];
static const CRGB kColorSequence[] = {
    CRGB::Red,
    CRGB::Green,
    CRGB::Blue,
    CRGB::White
};
static const char *const kColorNames[] = {
    "red",
    "green",
    "blue",
    "white"
};

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 2000) {
        delay(10);
    }

    FastLED.addLeds<NEOPIXEL, PIXEL_PIN>(pixels, NUM_PIXELS);
    FastLED.setBrightness(LED_BRIGHTNESS);

    Serial.println("ESP32-S3 Supermini RGB demo ready");
    Serial.print("RGB data pin: ");
    Serial.println(PIXEL_PIN);
}

void loop() {
    pixels[0] = CRGB::Red; FastLED.show(); delay(1000);
    pixels[0] = CRGB::Green; FastLED.show(); delay(1000);
    pixels[0] = CRGB::Blue; FastLED.show(); delay(1000);

    static size_t colorIndex = 0;

    pixels[0] = kColorSequence[colorIndex];
    FastLED.show();

    Serial.print("LED color: ");
    Serial.println(kColorNames[colorIndex]);

    colorIndex = (colorIndex + 1) % (sizeof(kColorSequence) / sizeof(kColorSequence[0]));
    delay(COLOR_SWITCH_DELAY_MS);
}
