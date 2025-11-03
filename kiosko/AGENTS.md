# Repository Guidelines

## Project Structure & Module Organization
- `src/app.py` — Flask application entry point (serves `/`).
- `src/requirements.txt` — Python dependencies (includes optional GUI/hardware libs).
- Recommended (if/when added): `src/templates/` for Jinja templates and `src/static/` for assets.
- Tests (recommended): `tests/` with `test_*.py` files.

## Build, Test, and Development Commands
- Create venv (Windows): `python -m venv .venv && .\.venv\Scripts\activate`
- Install deps: `pip install -r src/requirements.txt`
- Run locally: `python src/app.py` (binds `0.0.0.0:80`). On Windows, run an elevated shell or change the port to `5000` before committing when developing.
- Lint/format (suggested): `pip install black isort flake8` then `black src tests && isort src tests && flake8 src tests`

## Coding Style & Naming Conventions
- Python 3.10+; follow PEP 8 with 4-space indentation.
- Names: `snake_case` for modules/functions/variables; `PascalCase` for classes.
- Strings: use UTF-8 to avoid mojibake in Spanish text.
- Keep functions small; avoid committing unused optional dependencies unless required by code.

## Testing Guidelines
- Framework: `pytest` (recommended). Place tests in `tests/` named `test_*.py`.
- Run: `pytest -q` (install with `pip install pytest`).
- Target: route handlers and any utility code. Add fixtures for app/client as needed.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- Keep PRs focused and small. Include:
  - What changed and why
  - How to test (commands, expected result)
  - Screenshots/GIFs for UI-facing changes

## Security & Configuration Tips
- Do not commit secrets. Use environment variables and a local `.env` (via `python-dotenv`) for development.
- Example `.env` (if adopted): `FLASK_ENV=development`, `PORT=5000`.
- Prefer non-privileged ports in dev; only bind to `:80` in controlled environments.

## Agent-Specific Notes
- These guidelines apply to the entire repository.
- When adding modules, mirror the structure under `src/`; add tests alongside in `tests/`.
- Update `src/requirements.txt` when adding/removing dependencies and keep it minimal.

