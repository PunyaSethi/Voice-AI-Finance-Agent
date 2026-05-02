from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.observability.metrics import metrics_store
from app.utils.logger import get_logger
from app.voice.streaming import RealTimeVoicePipeline


router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    settings = get_settings()
    if settings.api_key:
        token = websocket.query_params.get("api_key") or websocket.headers.get("x-api-key") or websocket.headers.get("authorization")
        if not token or (token != settings.api_key and token != f"Bearer {settings.api_key}"):
            await websocket.close(code=4401)
            return

    await websocket.accept()
    try:
        pipeline = RealTimeVoicePipeline()
    except Exception as exc:
        logger.exception("Voice pipeline startup failed")
        await websocket.send_json({"error": str(exc)})
        await websocket.close()
        return

    try:
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break
            except RuntimeError as exc:
                if "disconnect message has been received" in str(exc).lower():
                    logger.info("WebSocket client disconnected")
                    break
                raise

            result = None

            try:
                if "bytes" in message and message["bytes"]:
                    pipeline.receive_audio_chunk(message["bytes"])
                    result = pipeline.process_if_ready()
                elif "text" in message and message["text"]:
                    if message["text"] == "flush":
                        result = pipeline.process_if_ready(force=True)
            except Exception as exc:
                logger.exception("Voice message processing failed")
                pipeline.clear_buffer()
                if websocket.client_state.name == "CONNECTED":
                    await websocket.send_json({"error": str(exc)})
                continue

            if result:
                metrics_store.increment("voice_sessions_completed")
                await websocket.send_json(result)

    except Exception as exc:
        logger.exception("WebSocket processing failed")
        if websocket.client_state.name == "CONNECTED":
            try:
                await websocket.send_json({"error": str(exc)})
            except Exception:
                logger.warning("Could not send websocket error response because the socket was already closing")
