"""Каркас FastAPI-застосунку. Екрани додають фічі дашборду."""

from fastapi import FastAPI

app = FastAPI(title="romis-rover-telemetry", docs_url=None, redoc_url=None)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
