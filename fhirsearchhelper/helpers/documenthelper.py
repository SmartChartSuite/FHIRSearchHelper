'''File to handle all operations around Medication-related Resources'''

import logging
from copy import deepcopy
from .operationoutcomehelper import handle_operation_outcomes

import requests
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType

logger: logging.Logger = logging.getLogger('fhirsearchhelper.documenthelper')

def expand_document_references(input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle | None:

    returned_resources: list[BundleEntryType] = input_bundle.entry
    output_bundle: dict = deepcopy(input_bundle).dict(exclude_none=True)
    expanded_entries = []

    for entry in returned_resources:
        entry = entry.dict(exclude_none=True) #type: ignore
        resource = entry['resource']
        if resource['resourceType'] == 'OperationOutcome':
            handle_operation_outcomes(resource=resource)
            continue
        for i, content in enumerate(resource['content']):
            if 'url' in content['attachment']:
                binary_url = content['attachment']['url']
                logger.debug(f'Querying {base_url+"/"+binary_url}')
                binary_url_lookup = requests.get(f'{base_url}/{binary_url}', headers=query_headers)
                if binary_url_lookup.status_code != 200:
                    logger.error(f'The query responded with a status code of {binary_url_lookup.status_code}')
                    if binary_url_lookup.status_code == 403:
                        logger.error('The 403 code typically means your defined scope does not allow for retrieving this resource. Please check your scope to ensure it includes Binary.Read.')
                        if 'WWW-Authenticate' in binary_url_lookup.headers:
                            logger.error(binary_url_lookup.headers['WWW-Authenticate'])
                    if binary_url_lookup.status_code == 400 and 'json' in binary_url_lookup.headers['content-type']:
                        logger.error(binary_url_lookup.json())
                if binary_url_lookup.status_code == 200 and 'json' in binary_url_lookup.headers['content-type']:
                    content_data = binary_url_lookup.json()['data']
                elif binary_url_lookup.status_code == 200:
                    content_data = binary_url_lookup.text
                else:
                    logger.debug('Setting content of DocumentReference to empty since Binary resource could not be retrieved')
                    content_data: str = ''
                resource['content'][i]['attachment']['data'] = content_data
                del resource['content'][i]['attachment']['url']
        entry['resource'] = resource
        expanded_entries.append(entry)

    output_bundle['entry'] = expanded_entries

    return Bundle.parse_obj(output_bundle)
