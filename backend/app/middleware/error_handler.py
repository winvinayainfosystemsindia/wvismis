"""Global error handling middleware"""

from typing import Callable
from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
from loguru import logger
from app.middleware.exceptions import AppError


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle unexpected exceptions and return standardized error responses"""

    async def dispatch(self, request: Request, call_next: Callable):
        try:
            return await call_next(request)

        except AppError as e:
            logger.warning(f"Application error on {request.url.path}: {e.message} (status {e.status_code})")
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.error_code,
                    "message": e.message,
                    "detail": e.detail,
                },
            )

        except ValidationError as e:
            logger.error(f"Validation error on {request.url.path}: {str(e)}")
            safe_errors = e.errors(include_input=False, include_context=False)
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=jsonable_encoder({
                    "error": "Validation Error",
                    "detail": safe_errors,
                    "message": "Invalid input data",
                }),
            )

        except SQLAlchemyError as e:
            logger.error(f"Database error on {request.url.path}: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Database Error",
                    "message": "A database error occurred. Please try again later.",
                },
            )

        except ValueError as e:
            logger.error(f"Value error on {request.url.path}: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Bad Request",
                    "message": str(e),
                },
            )

        except Exception as e:
            logger.exception(f"Unhandled exception on {request.url.path}: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred. Please try again later.",
                },
            )
