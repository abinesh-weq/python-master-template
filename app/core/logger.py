import logging
import sys
from pathlib import Path
from typing import Optional
from loguru import logger

from app.core.config import settings


class CustomLogger:
    """
    Sophisticated logging configuration equivalent to Java's logback-spring.xml.
    Supports different log levels, file rotation, and structured logging.
    """

    def __init__(self, name: str):
        self.name = name
        self._setup_logger()

    def _setup_logger(self):
        """Configure logger with custom formatting and handlers"""
        # Remove default handlers
        logger.remove()
        
        # Console handler with formatting
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        
        logger.add(
            sys.stderr,
            format=log_format,
            level="DEBUG" if settings.DEBUG else "INFO",
            colorize=True,
            backtrace=True,
            diagnose=True
        )
        
        # File handler with rotation for production
        if not settings.DEBUG:
            log_file = Path("logs") / f"{self.name}.log"
            log_file.parent.mkdir(exist_ok=True)
            
            logger.add(
                log_file,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
                level="INFO",
                rotation="10 MB",
                retention="30 days",
                compression="zip"
            )

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        logger.exception(message, **kwargs)

    def audit(self, action: str, user_uuid: Optional[str] = None, **kwargs):
        """Log audit event"""
        audit_data = {
            "action": action,
            "user_uuid": user_uuid,
            "timestamp": logger._core.now().isoformat(),
            **kwargs
        }
        logger.info(f"AUDIT: {action}", extra={"audit": audit_data})


# Global logger instance
def get_logger(name: str) -> CustomLogger:
    """Get configured logger instance"""
    return CustomLogger(name)


# Default application logger
app_logger = get_logger("weq-backend")
