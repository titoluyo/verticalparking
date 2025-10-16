# Repository Guidelines

## Project Structure & Module Organization
- `cabina/` hosts the main cabin sensor Arduino sketches; `cabina.ino` targets ESP32-S3 with FastLED while `cabina_c6.ino` adapts pin maps for ESP32-C6.
- `arduino/SENSOR_DISTANCIA_VL53L0X/` demos the VL53L0X range finder and stays isolated for bench experiments.
- `esp32s3-blink/` and `esp32c6-blink/` are PlatformIO environments with `src/`, `include/`, `lib/`, and `test/`; keep board-specific wiring notes beside each project.
- Use `.pio/` build artifacts only for troubleshooting; regenerate by rerunning PlatformIO commands instead of editing outputs manually.

## Build, Test, and Development Commands
- `pio run -e esp32s3-supermini` (or `esp32c6-supermini`) compiles the selected PlatformIO target; append `-t upload` to flash the board.
- `pio device monitor -e esp32s3-supermini` attaches the serial console at 115200 baud; press Ctrl+] to exit.
- `arduino-cli compile --fqbn esp32:esp32:esp32s3 cabina/cabina.ino` builds the S3 sketch; swap the FQBN for C6 variants before uploading.
- Run `pio run -t clean` whenever library flags or board configs change to avoid stale objects.

## Coding Style & Naming Conventions
- Arduino sketches follow K&R braces with two-space indents; C++ in PlatformIO may use four spaces where clarity improves nesting.
- Declare hardware constants as uppercase macros (`LED_PIN`, `DATA_PIN`) and keep functions/variables camelCase.
- Prefer concise `Serial.print` logs; add bilingual notes only when clarifying field procedures.

## Testing Guidelines
- Place Unity tests in `test/` using the `<feature>_test.cpp` pattern and include `ArduinoFake` helpers when mocking IO.
- Execute `pio test -e esp32s3-supermini` to run the suite; rerun on both environments when shared modules change.
- Capture manual checks—LED blink timings, sensor ranges, wiring photos—in the PR description when automation is not feasible.

## Commit & Pull Request Guidelines
- Use short, imperative commit titles (e.g., `ajusta leds supermini`); group related file changes within one commit.
- PRs must list target hardware, relevant build/test output, and any wiring or library dependencies; attach serial traces or photos for firmware-visible behavior.
- Rebase before requesting review to keep the history linear and highlight only the intended diff.

## Firmware & Configuration Tips
- Default serial monitors to 115200 baud; adjust sketches if your host requires another speed.
- Record pin assignments in-code comments when swapping between Supermini revisions; update `platformio.ini` if upload speed or board ID changes.
- Store sensitive Wi-Fi credentials in local `platformio.ini` extra configs, never in tracked sources.
