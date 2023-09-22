'''Main file for entrypoint to package'''

import logging

import requests
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.capabilitystatement import CapabilityStatement
from fhir.resources.R4B.fhirtypes import Id
from fhir.resources.R4B.operationoutcome import OperationOutcome

from .helpers.capabilitystatement import get_supported_search_params, load_capability_statement
from .helpers.fhirfilter import filter_bundle
from .helpers.gapanalysis import run_gap_analysis
from .helpers.medicationhelper import expand_medication_references
from .helpers.documenthelper import expand_document_references
from .models.models import CustomFormatter, QuerySearchParams, SupportedSearchParams

logger: logging.Logger = logging.getLogger('fhirsearchhelper')
logger.setLevel(logging.INFO)
ch: logging.StreamHandler = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

# Epic IDs are sometimes more than the max_length of 64 set in the default
Id.configure_constraints(max_length=256)


def run_fhir_query(base_url: str = None, query_headers: dict[str, str] = None, search_params: QuerySearchParams = None, query: str = None, # type: ignore
                   capability_statement_file: str = None, capability_statement_url: str = None, debug: bool = False) -> Bundle | OperationOutcome | None: # type: ignore
    '''
    Entry function to run FHIR query using a CapabilityStatement and returning filtered resources
    WARNING: There is currently not a way to use a CapabilityStatement out of the box. See README.md of source for details.
    '''

    if debug:
        logger.info('Logging level is being set to DEBUG')
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.addHandler(ch)

    # Error handling
    if not base_url and not search_params and not query:
        raise ValueError('You must provide either a base_url and a dictionary of search parameters or the full query string in the form of <baseUrl>/<resourceType>?<param1>=<value1>&...')

    cap_state: CapabilityStatement = load_capability_statement(url=capability_statement_url, file_path=capability_statement_file)
    supported_search_params: list[SupportedSearchParams] = get_supported_search_params(cap_state)

    pretty_supported_search_params = {resource_params['resourceType']: [item['name'] for item in resource_params['searchParams']]
                                                                        for resource_params in [item.dict(exclude_none=True) for item in supported_search_params]}

    logger.debug(f'Supported search parameters for this server are: {pretty_supported_search_params}')

    if query:
        url_res, q_search_params = query.split('?')
        if url_res.split("/")[-1] not in pretty_supported_search_params:
            logger.error(f'Resource {url_res.split("/")[-1]} is not supported for searching, returning empty Bundle')
            return Bundle(**{'type': 'searchset', 'total': 0, 'link': [{'relation': 'self', 'url': url_res}]})
        if not q_search_params:
            logger.error('No search params, Epic does not support pulling all resources of a given type with no search parameters. Please refine your query.')
            new_query_response = requests.get(f'{url_res}', headers=query_headers)
            if new_query_response.status_code == 403:
                logger.error(f'The query responded with a status code of {new_query_response.status_code}')
                if 'WWW-Authenticate' in new_query_response.headers:
                    logger.error(f'WWW-Authenticate Error: {new_query_response.headers["WWW-Authenticate"]}')
                return None
            elif new_query_response.status_code == 400:
                return OperationOutcome(**new_query_response.json())
            else:
                return None

        base_url = '/'.join(url_res.split('/')[:-1])
        q_resource_type = url_res.split('/')[-1]
        search_params_list: list[str] = q_search_params.split('&')
        search_params_dict: dict[str, str] = {item.split('=')[0]: item.split('=')[1] for item in search_params_list}
        search_params: QuerySearchParams = QuerySearchParams(resourceType=q_resource_type, searchParams=search_params_dict)

    logger.debug(f'Search parameters for this request are: {search_params}')

    gap_output: list[str] = run_gap_analysis(supported_search_params=supported_search_params, query_search_params=search_params)

    logger.debug(f'Gap output from these two sets of search parameters is: {gap_output}')

    new_query_params_str = '&'.join([f'{key}={value}' for key, value in search_params.searchParams.items() if key not in gap_output])
    if new_query_params_str:
        new_query_string = f'{search_params.resourceType}?{new_query_params_str}'
    else:
        new_query_string = search_params.resourceType

    # new_query_string = new_query_string.replace('%7C', '|')

    logger.debug(f'New query string is {new_query_string}')

    logger.debug(f'Making request to {base_url}/{new_query_string}')
    new_query_response = requests.get(f'{base_url}/{new_query_string}', headers=query_headers)
    if new_query_response.status_code != 200:
        logger.error(f'The query responded with a status code of {new_query_response.status_code}')
        if 'WWW-Authenticate' in new_query_response.headers:
            logger.error(f'WWW-Authenticate Error: {new_query_response.headers["WWW-Authenticate"]}')
        return None

    new_query_response_bundle: Bundle | None = Bundle.parse_obj(new_query_response.json())

    if not new_query_response_bundle.entry:
        return new_query_response_bundle

    if 'operationoutcome' in [entry.resource.resource_type.lower() for entry in new_query_response_bundle.entry]:  #type: ignore
        new_query_response_bundle.entry = []

    if 'MedicationRequest' in new_query_string:
        logger.debug('Resources are of type MedicationRequest, proceeding to expand MedicationReferences')
        new_query_response_bundle = expand_medication_references(input_bundle=new_query_response_bundle, base_url=base_url, query_headers=query_headers)
        if not new_query_response_bundle:
            return None

    if 'DocumentReference' in new_query_string:
        logger.debug('Resources are of type DocumentReference, proceeding to expand DocumentReferences')
        new_query_response_bundle = expand_document_references(input_bundle=new_query_response_bundle, base_url=base_url, query_headers=query_headers)
        if not new_query_response_bundle:
            return None

    logger.debug(f'Size of bundle before filtering is {new_query_response_bundle.total} resources')
    filtered_bundle: Bundle = filter_bundle(input_bundle=new_query_response_bundle, search_params=search_params, gap_analysis_output=gap_output)
    logger.debug(f'Size of bundle after filtering is {filtered_bundle.total} resources')

    return filtered_bundle
