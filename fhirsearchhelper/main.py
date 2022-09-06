'''Main file for entrypoint to package'''

from .helpers.capabilitystatement import load_capability_statement, get_supported_search_params

from .models.models import QuerySearchParams


def run_fhir_query(query: str, capability_statement_file: str = None, capability_statement_url: str = None) -> None:
    '''Entry function to run FHIR query using a CapabilityStatement and returning filtered resources'''

    cap_state = load_capability_statement(url=capability_statement_url, file_path=capability_statement_file)
    supported_search_params = get_supported_search_params(cap_state)

    resource_type, search_params = query.split('?')  # Query should be of form: Observation?code=12345-6&category=vital-signs&...
    search_params = search_params.split('&')
    search_params = [{'parameter': item.split('=')[0], 'value': item.split('=')[1]} for item in search_params]
    search_params = QuerySearchParams(resourceType=resource_type, searchParams=search_params)

    # TODO
