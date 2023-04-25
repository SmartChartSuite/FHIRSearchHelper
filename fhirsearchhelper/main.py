'''Main file for entrypoint to package'''

from fhir.resources.R4B.capabilitystatement import CapabilityStatement
from fhir.resources.R4B.bundle import Bundle
import requests

from helpers.capabilitystatement import load_capability_statement, get_supported_search_params

from models.models import QuerySearchParams, SupportedSearchParams
from helpers.gapanalysis import run_gap_analysis
from helpers.fhirfilter import filter_bundle


def run_fhir_query(base_url: str = None, query_headers: dict[str, str] = None, resource_type: str = None, search_params: QuerySearchParams = None, query: str = None, # type: ignore
                   capability_statement_file: str = None, capability_statement_url: str = None) -> Bundle | None: # type: ignore
    '''
    Entry function to run FHIR query using a CapabilityStatement and returning filtered resources
    WARNING: There is currently not a way to use a CapabilityStatement out of the box. See README.md of source for details.
    '''

    # Error handling
    if not base_url and not resource_type and not search_params and not query:
        raise ValueError('You must provide either a base_url, resource_type, and a dictionary of search parameters or the full query string'
                         'in the form of <baseUrl>/<resourceType>?<param1>=<value1>&...')
    if not query and not all([resource_type, search_params]):
        raise ValueError('You must provide both a resourceType and a dictionary of search parameters if you do not pass a full query string.')

    cap_state: CapabilityStatement = load_capability_statement(url=capability_statement_url, file_path=capability_statement_file)
    supported_search_params: list[SupportedSearchParams] = get_supported_search_params(cap_state)

    if query:
        url_split: list[str] = query.split('/')
        base_url: str = '/'.join(url_split[:-1])
        query_url: str = url_split[-1]
        query_split: list[str] = query_url.split('?')  # Query should be of form: Observation?code=12345-6&category=vital-signs&...
        q_resource_type: str = query_split[0]
        q_search_params: str = query_split[1]
        search_params_list: list[str] = q_search_params.split('&')
        search_params_dict: dict[str, str] = {item.split('=')[0]: item.split('=')[1] for item in search_params_list}
        search_params: QuerySearchParams = QuerySearchParams(resourceType=q_resource_type, searchParams=search_params_dict)

    gap_output: list[str] = run_gap_analysis(supported_search_params=supported_search_params, query_search_params=search_params)

    new_query_params_str = '&'.join([f'{key}={value}' for key, value in search_params.searchParams.items() if key not in gap_output])
    if new_query_params_str:
        new_query_string = f'{search_params.resourceType}?{new_query_params_str}'
    else:
        new_query_string = search_params.resourceType

    new_query_response = requests.get(f'{base_url}/{new_query_string}', headers=query_headers)
    if new_query_response.status_code != 200:
        print(f'The query responded with a status code of {new_query_response.status_code}')
        return None
    new_query_response_bundle = Bundle.parse_obj(new_query_response.json())

    filtered_bundle = filter_bundle(input_bundle=new_query_response_bundle, search_params=search_params, gap_analysis_output=gap_output)
    return filtered_bundle
