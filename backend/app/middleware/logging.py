"""Request/Response logging middleware with tenant and request ID tracking"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming HTTP requests and outgoing responses"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        org_header = request.headers.get("X-Organization-ID") or request.headers.get("X-Organization-Slug")

        logger.bind(
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            organization_header=org_header,
            client_ip=request.client.host if request.client else None,
        ).info("Incoming request")

        start_time = time.time()

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            logger.bind(
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration=f"{process_time:.3f}s",
            ).info("Request completed")

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.bind(
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                duration=f"{process_time:.3f}s",
                error=str(e),
            ).error("Request failed")
            raise
