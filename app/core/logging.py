import logging
from logging.config import dictConfig

from app.core.configs import DevConfig, TestConfig, ProdConfig, settings


def obfuscated(email: str, non_obfuscated_length: int, min_obfuscation: int = 8) -> str:
    first_part, domain = email.split("@")
    if len(first_part) <= non_obfuscated_length+min_obfuscation:
        non_obfuscated_length = 1
    return first_part[:non_obfuscated_length] + "*"*min_obfuscation + first_part[-1:] + "@" + domain


class EmailObfuscationFilter(logging.Filter):
    def __init__(self, name: str = "", non_obfuscated_length: int = 3) -> None:
        super().__init__(name)
        self.non_obfuscated_length = non_obfuscated_length

    def filter(self, record: logging.LogRecord) -> bool:
        if "email" in record.__dict__:
            record.email = obfuscated(record.email, self.non_obfuscated_length)
        return True


handlers = ["default", "rotating_file"]
# TODO: when prod env, implement logging to AWS/S3/CloudWatch


def configure_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "correlation_id": {
                    "()": "asgi_correlation_id.CorrelationIdFilter",
                    "uuid_length": 8 if isinstance(settings, DevConfig) else 32,
                    "default_value": "-",
                },
                "email_obfuscation": {
                    "()": EmailObfuscationFilter,
                    "non_obfuscated_length": 2 if isinstance(settings, DevConfig) else 0,
                },
            },
            "formatters": {
                "console": {
                    "class": "logging.Formatter",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                    "format": "(%(correlation_id)s) %(name)s:%(lineno)d - %(message)s",
                },
                "file": {
                    "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                    "format": "%(asctime)s %(levelname)s %(correlation_id)s %(name)s %(lineno)d %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "class": "rich.logging.RichHandler",
                    "level": "DEBUG",
                    "formatter": "console",
                    "filters": ["correlation_id", "email_obfuscation"]
                },
                "rotating_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "DEBUG",
                    "formatter": "file",
                    "filename": "logs/storeapi.log",
                    "maxBytes": 1024 * 1024,  # 1MB
                    "backupCount": 5,
                    "encoding": "utf8",
                    "filters": ["correlation_id", "email_obfuscation"]
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default", "rotating_file"], "level": "INFO"},
                "src": {
                    "handlers": handlers,
                    "level": "DEBUG" if (isinstance(settings, DevConfig) or isinstance(settings, TestConfig)) else "INFO",
                    "propagate": False
                },
            }
        }
    )
