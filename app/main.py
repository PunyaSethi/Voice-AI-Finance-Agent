from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import public_router, router as api_router
from app.api.websocket import router as ws_router
from app.config import get_settings
from app.db.database import init_db
from app.observability.middleware import RequestContextMiddleware
from app.utils.logger import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db()

    app = FastAPI(
        title=settings.app_name,
        description="Modular multi-agent backend for voice-based finance assistance.",
        version=settings.app_version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.mount("/audio", StaticFiles(directory=settings.audio_output_dir), name="audio")
    app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")
    app.include_router(public_router, prefix="/api")
    app.include_router(api_router, prefix="/api")
    app.include_router(ws_router)

    return app


app = create_app()


@app.get("/")
def root():
    return {"status": "ok", "service": get_settings().app_name}
