"""File for custom models"""

import logging

from fhir.resources.R4B.capabilitystatement import CapabilityStatementRestResourceSearchParam
from pydantic import BaseModel


class CustomFormatter(logging.Formatter):
    grey: str = "\x1b[38;21m"
    green: str = "\x1b[32m"
    yellow: str = "\x1b[33m"
    red: str = "\x1b[31m"
    bold_red: str = "\x1b[31;1m"
    reset: str = "\x1b[0m"
    format_str: str = "{asctime}   {levelname:8s} --- {name}: {message}"

    FORMATS: dict[int, str] = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record) -> str:
        log_fmt: str | None = self.FORMATS.get(record.levelno)
        formatter: logging.Formatter = logging.Formatter(log_fmt, "%m/%d/%Y %I:%M:%S %p", style="{")
        return formatter.format(record)


class SupportedSearchParams(BaseModel):
    resourceType: str
    searchParams: list[CapabilityStatementRestResourceSearchParam]


class QuerySearchParams(BaseModel):
    resourceType: str
    searchParams: dict[str, str]
