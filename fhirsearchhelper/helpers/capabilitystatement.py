"""File to handle all operations around a CapabilityStatement"""

import logging
import os
from pathlib import Path

from fhir.resources.R4B.capabilitystatement import CapabilityStatement
from requests import Session

from ..models.models import SupportedSearchParams

logger: logging.Logger = logging.getLogger("fhirsearchhelper.capabilitystatement")


def load_capability_statement(session: Session, url: str | None = None, file_path: str | None = None) -> CapabilityStatement:
    """Function to load a CapabilityStatement into memory"""

    if url and file_path:
        logger.info("Defaulting to url...")

    if url:
        try:
            cap_statement: dict = session.get(url, headers={"Accept": "application/json"}).json()
        except Exception as exc:
            logger.error("Something went wrong trying to access the CapabilityStatement via URL")
            raise exc

        try:
            cap_statement_object: CapabilityStatement = CapabilityStatement.parse_obj(cap_statement)
        except Exception as exc:
            logger.error("Something went wrong when trying to turn the retrieved cap statement into a CapabilityStatement object")
            raise exc
    elif file_path:
        if os.path.isfile(f"{Path(__file__).parents[1]}/capabilitystatements/{file_path}"):
            logger.info(f"Found file {file_path} in the CapabilityStatements folder")
            file_path = f"{Path(__file__).parents[1]}/capabilitystatements/{file_path}"
        cap_statement_object = CapabilityStatement.parse_file(file_path)
    else:
        raise ValueError("You need to pass a url, an option to specify a preloaded CapabilityStatement, or a file path.")

    return cap_statement_object


def get_supported_search_params(cs: CapabilityStatement) -> list[SupportedSearchParams]:
    """Function to pull out supported search parameters from a capability statement"""

    return [SupportedSearchParams(resourceType=resource.type, searchParams=resource.searchParam) for resource in cs.rest[0].resource if resource.searchParam]  # type: ignore
