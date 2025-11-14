# Repository Guidelines

## Project Structure & Module Organization
- `api/` hosts the FastAPI service (`app/main.py`) plus helper scripts (`setup_env.sh`, `start_server.sh`).
- `kiosko/` is the Flask UI with `app/`, `static/`, `templates/`, and Pi startup scripts.
- `cabinasensor/` groups embedded firmware: Arduino sketches, CircuitPython prototypes, and PlatformIO builds for ESP32-S3 (`esp32s3-blink/`) and ESP32-C6 (`esp32c6-blink/`).
- Docs and CAD stay under `docs/` and `diseno3d/`; keep new artifacts there.

## Build, Test, and Development Commands
- API: `bash api/setup_env.sh`, then `PORT=8000 bash api/start_server.sh` or `source api/.venv/bin/activate && uvicorn app.main:app --reload`.
- Kiosko: `python3 -m venv kiosko/.venv && source kiosko/.venv/bin/activate`, `pip install -r kiosko/requirements.txt`, `python kiosko/app.py`; on kiosks run `kiosko/start_kiosko.sh` so logs land in `kiosko/logs/`.
- Sensors: run `pio run -e esp32s3-supermini` or `pio run -e esp32c6-supermini`, then `pio run -t upload` and `pio device monitor -b 115200`.

## Coding Style & Naming Conventions
- Python (3.10+) follows PEP 8, 4-space indents, type hints on public APIs, and docstrings; run `black` + `isort`.
- Embedded C/C++ keeps `snake_case` functions, `UPPER_CASE` macros, and minimal globals; format via `platformio clang-format` or the Arduino formatter.
- Name directories lowercase-hyphen and mirror the existing package hierarchy when adding modules.

- Python services rely on `pytest`; place suites in `tests/` beside `api/` and `kiosko/` packages, name files `test_<feature>.py`, and run `pytest -q` from the repo root with the right venv active.
- Firmware validation uses PlatformIO: keep Unity-style cases under `test/` per board, run `pio test -e <env>`, and fall back to serial macros or CircuitPython REPLs for quick checks.
- Prioritize coverage of API routes, DB helpers, and safety-critical drivers (lift triggers, range thresholds) before auxiliary helpers.

## Commit & Pull Request Guidelines
- History favors short, lowercase imperatives (`cabina_mqtt`, `temp`); prefer `component: action` (e.g., `api: add slot endpoint`) to telegraph scope.
- PRs must explain why the change exists, how it was tested (commands/logs/screenshots), and where to find artifacts.
- Reference related issues and flag follow-up tasks so hardware and software deployments stay synchronized.

## Security & Configuration Tips
- Never commit API keys, Wi-Fi credentials, or device tokens; keep them in untracked `.env` files and load with env vars such as `PORT`, `SECRET_KEY`, and MQTT auth fields.
- Rotate kiosk secrets when imaging SD cards and scrub `kiosko/logs/` before handing logs to third parties.
- Stick to the documented PlatformIO upload speeds and lock down USB access to avoid leaving ESP boards in bootloader mode.
