import logging
import traceback
from functools import partial

import click

from . import context


def _format_tb(exc):
    # see https://peps.python.org/pep-3134/
    if exc is None:
        return []

    tb = traceback.format_tb(exc.__traceback__)

    if exc.__context__:
        tb.append(f"{type(exc.__context__).__name__}: {exc.__context__}")
        tb += _format_tb(exc.__context__)

    return tb


def _get_exception(record: logging.LogRecord):
    exc_info = getattr(record, "exc_info", None)
    if not exc_info:
        return None, None, None

    type, exc, _ = exc_info
    record.exc_info = None

    return (
        type.__name__,
        # https://github.com/encode/starlette/blob/master/starlette/exceptions.py
        getattr(exc, "detail", exc),
        _format_tb(exc),
    )


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord):
        record.correlation_id = context.current_headers().get("x-correlation-id")
        return True


class ConsoleLogFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: partial(click.style, fg="cyan"),
        logging.INFO: partial(click.style, fg="green"),
        logging.WARNING: partial(click.style, fg="yellow"),
        logging.ERROR: partial(click.style, fg="red"),
        logging.CRITICAL: partial(click.style, fg="bright_red"),
    }

    def __init__(self, fmt=None, datefmt=None, style="%", *args, **kwargs):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def color_level_name(self, level_name, level_no):
        func = self.level_name_colors.get(level_no, str)
        return func(level_name)

    def formatMessage(self, record: logging.LogRecord):
        levelname = record.levelname

        levelname = self.LEVEL_COLORS[record.levelno](levelname)
        record.levelprefix = f"{levelname:16}"
        return super().formatMessage(record)

    def format(self, record: logging.LogRecord):
        exception, value, tb = _get_exception(record)

        correlation_id = getattr(record, "correlation_id") or "-" * 6
        record.name = f"[{click.style(correlation_id, fg='magenta'):6}] " + record.name

        return "".join(
            (
                super().format(record),
                "\n" + "\n".join(tb) if tb else "",
                f"\n{exception}" if exception else "",
                f": {value}" if value else "",
            )
        )


LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": True,
    "filters": {"correlation_id": {"()": CorrelationIdFilter}},
    "formatters": {
        "text": {
            "()": ConsoleLogFormatter,
            "fmt": "%(name)-25s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "()": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "text",
            "filters": ["correlation_id"],
        }
    },
    "root": {
        "level": logging.DEBUG,
        "handlers": ["console"],
    },
    "loggers": {
        "uvicorn": {"level": logging.DEBUG},
        "svc": {"level": logging.DEBUG},
        "client": {"level": logging.DEBUG},
        "crud": {"level": logging.DEBUG},
        "cache": {"level": logging.DEBUG},
    },
}
