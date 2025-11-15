from fastapi import FastAPI

app = FastAPI(title="Vertical Parking API", version="0.1.0")


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    """Return a minimal status payload for uptime checks."""
    return {"status": "ok", "service": "vertical-parking"}


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Simple liveness endpoint used by monitoring."""
    return {"status": "healthy"}
