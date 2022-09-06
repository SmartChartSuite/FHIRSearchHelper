'''File to handle all operations around a CapabilityStatement'''

from fhir.resources.capabilitystatement import CapabilityStatement

from ..models.models import SupportedSearchParams


def load_capability_statement(url: str = None, file_path: str  = None) -> CapabilityStatement:
    '''Function to load a CapabilityStatement into memory'''

    if not url and not file_path:
        raise ValueError('You need to pass a url, an option to specify a preloaded CapabilityStatement, or a file path.')

    if url and file_path:
        print('Defaulting to url...')

    # TODO

    return CapabilityStatement()


def get_supported_search_params(cs: CapabilityStatement) -> SupportedSearchParams:
    '''Function to pull out supported search parameters from a capability statement'''

    # TODO
