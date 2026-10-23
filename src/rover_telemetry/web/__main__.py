"""Точка входу `python -m rover_telemetry.web` (uvicorn)."""

import uvicorn


def main() -> None:
    uvicorn.run("rover_telemetry.web.app:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
