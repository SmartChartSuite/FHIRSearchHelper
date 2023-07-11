'''File to handle all operations around a CapabilityStatement'''

import logging
import os
from pathlib import Path

import requests
from fhir.resources.R4B.capabilitystatement import CapabilityStatement

from ..models.models import SupportedSearchParams

logger: logging.Logger = logging.getLogger('fhirsearchhelper.capabilitystatement')


def load_capability_statement(url: str = None, file_path: str  = None) -> CapabilityStatement: # type: ignore
    '''Function to load a CapabilityStatement into memory'''

    if not url and not file_path:
        raise ValueError('You need to pass a url, an option to specify a preloaded CapabilityStatement, or a file path.')

    if url and file_path:
        logger.info('Defaulting to url...')

    if url:
        try:
            cap_statement: dict = requests.get(url, headers={'Accept': 'application/json'}).json()
        except Exception as exc:
            logger.error('Something went wrong trying to access the CapabilityStatement via URL')
            raise exc

        try:
            cap_statement_object: CapabilityStatement = CapabilityStatement.parse_obj(cap_statement)
        except Exception as exc:
            logger.error('Something went wrong when trying to turn the retrieved cap statement into a CapabilityStatement object')
            raise exc
    else:
        if os.path.isfile(f'{Path(__file__).parents[1]}/capabilitystatements/{file_path}'):
            logger.info(f'Found file {file_path} in the CapabilityStatements folder')
            file_path = f'{Path(__file__).parents[1]}/capabilitystatements/{file_path}'
        cap_statement_object = CapabilityStatement.parse_file(file_path)

    return cap_statement_object


def get_supported_search_params(cs: CapabilityStatement) -> list[SupportedSearchParams]:
    '''Function to pull out supported search parameters from a capability statement'''

    return [SupportedSearchParams(resourceType=resource.type, searchParams=resource.searchParam) for resource in cs.rest[0].resource if resource.searchParam] # type: ignore
