import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

DEFAULT_STATIC_DIR = Path(__file__).parent / "static"


def create_app(static_dir: Path | None = None) -> FastAPI:
    application = FastAPI(title="Project Management MVP")

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    application.mount(
        "/",
        StaticFiles(directory=static_dir or DEFAULT_STATIC_DIR, html=True),
        name="frontend",
    )
    return application


app = create_app(Path(os.environ.get("STATIC_DIR", DEFAULT_STATIC_DIR)))