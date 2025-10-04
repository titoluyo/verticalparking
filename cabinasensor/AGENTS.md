# Repository Guidelines

## Project Structure & Module Organization
- `cabina/` holds Arduino sketches for the cabin sensor; `cabina.ino` targets ESP32-S3 with FastLED, while `cabina_c6.ino` adapts for ESP32-C6.
- `arduino/SENSOR_DISTANCIA_VL53L0X/` contains the VL53L0X distance demo.
- `esp32c6-blink/` and `esp32s3-blink/` are PlatformIO projects with standard `src/`, `include/`, `lib/`, and `test/` folders. Keep peripheral-specific assets beside their project.

## Build, Test, and Development Commands
- From a PlatformIO folder run `pio run -e esp32c6-supermini` or `pio run -e esp32s3-supermini` to compile, and append `-t upload` to flash the target module.
- Use `pio device monitor -e esp32c6-supermini` (or s3 variant) for serial logs; default speeds are 115200 baud.
- Arduino sketches compile via the IDE, or with `arduino-cli compile --fqbn esp32:esp32:esp32s3 cabina/cabina.ino` (adjust the `--fqbn` to match your board before uploading).

## Coding Style & Naming Conventions
- Follow K&R braces with two-space indentation inside Arduino files; C++ sources under PlatformIO may use four spaces where needed.
- Prefer descriptive uppercase macros for pins and constants (`DATA_PIN`, `LED_PIN`) and camelCase for variables/functions.
- Keep logging via `Serial.print` or `ESP_LOGI` concise and bilingual when needed; favor English for new additions.

## Testing Guidelines
- PlatformIO environments ship with Unity-based test hooks. Place unit tests in `test/` and name files `<feature>_test.cpp`.
- Run `pio test -e esp32c6-supermini` to execute tests; add board fakes or mocks when hardware access is required.
- Document manual validation steps (e.g., LED patterns, sensor ranges) in the PR if automated coverage is not feasible.

## Commit & Pull Request Guidelines
- Match the existing history: short, action-focused messages in the imperative (`arduino carpeta renombrado` style). Reference issues when available.
- Each PR should describe hardware targets, include build/test output snippets, and attach photos or serial traces for firmware features.
- Request review once the branch is rebased and PlatformIO builds pass. Note dependencies on external libraries or hardware setup changes.

## Firmware Notes
- Set monitor speeds to 115200 baud for ESP32 targets. For VL53L0X, confirm `Serial.begin(9600)` matches your host if you modify it.
- Keep board-specific pin assignments documented in-code comments and update platform specs when migrating between C6 and S3 modules.
