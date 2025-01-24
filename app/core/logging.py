import logging
import sys
from typing import Optional
import pydantic
from pathlib import Path

class LogConfig(pydantic.BaseModel):
    """Logging configuration to be set for the server"""
    LOGGER_NAME: str = "llm_server"
    LOG_FORMAT: str = "%(levelprefix)s | %(asctime)s | %(message)s"
    LOG_LEVEL: str = "DEBUG"

    # Get project root directory
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    LOG_DIR = PROJECT_ROOT / "logs"

    # Logging config
    version: int = 1
    disable_existing_loggers: bool = False
    formatters: dict = {
        "default": {
            "format": LOG_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }
    handlers: dict = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "formatter": "default",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "app.log"),
            "maxBytes": 10000000,  # 10MB
            "backupCount": 5,
        },
    }
    loggers: dict = {
        LOGGER_NAME: {"handlers": ["default", "file"], "level": LOG_LEVEL},
    }

def setup_logging(config: Optional[LogConfig] = None) -> None:
    """Configure logging for the application"""
    if config is None:
        config = LogConfig()
    
    # Ensure log directory exists
    config.LOG_DIR.mkdir(exist_ok=True)
    
    logging.config.dictConfig(config.model_dump())
    logger = logging.getLogger(config.LOGGER_NAME)
    
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_exception