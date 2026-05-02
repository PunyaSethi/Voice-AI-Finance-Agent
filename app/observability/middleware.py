from __future__ import annotations

import json
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.context import request_id_var
from app.observability.metrics import metrics_store
from app.utils.logger import get_logger


logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        response: Response | None = None

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            metrics_store.increment("http_requests_total")
            metrics_store.observe("http_request_duration_ms", elapsed_ms)
            logger.exception(
                json.dumps(
                    {
                        "event": "http_request_error",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(elapsed_ms, 2),
                    }
                )
            )
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            if response is not None:
                metrics_store.increment("http_requests_total")
                metrics_store.observe("http_request_duration_ms", elapsed_ms)
                logger.info(
                    json.dumps(
                        {
                            "event": "http_request",
                            "request_id": request_id,
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": response.status_code,
                            "duration_ms": round(elapsed_ms, 2),
                        }
                    )
                )
                response.headers["X-Request-ID"] = request_id
            request_id_var.reset(token)

        return response
