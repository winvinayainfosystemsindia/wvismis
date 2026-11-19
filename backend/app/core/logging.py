"""Logging configuration with structured JSON and colored console output using Loguru"""

import sys
import logging
from pathlib import Path
from loguru import logger
from app.core.config import settings


class InterceptHandler(logging.Handler):
    """Intercept standard Python logging messages and redirect to Loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    """Configure application logging with file rotation and retention"""
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # File handler
    log_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        if settings.LOG_FORMAT == "text"
        else "{message}"
    )

    logger.add(
        settings.LOG_FILE,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        format=log_format,
        level=settings.LOG_LEVEL,
        serialize=settings.LOG_FORMAT == "json",
        backtrace=True,
        diagnose=settings.DEBUG,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]:
        logging.getLogger(logger_name).handlers = [InterceptHandler()]

    logger.info(
        f"Logging configured - Environment: {settings.ENVIRONMENT}, Level: {settings.LOG_LEVEL}, Format: {settings.LOG_FORMAT}"
    )


def get_logger(name: str):
    """Get a bound logger instance"""
    return logger.bind(name=name)
