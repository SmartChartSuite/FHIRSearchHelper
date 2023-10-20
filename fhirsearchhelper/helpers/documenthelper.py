'''File to handle all operations around Medication-related Resources'''

import base64
import logging
from copy import deepcopy

import html2text
import requests
from fhir.resources.R4B.bundle import Bundle

from .operationoutcomehelper import handle_operation_outcomes

logger: logging.Logger = logging.getLogger('fhirsearchhelper.documenthelper')


def expand_document_reference_content(resource: dict, base_url: str, query_headers: dict) -> dict:
    """
    Expand content attachments of a DocumentReference resource into data fields.

    This function takes a DocumentReference resource and, for each content attachment that has a URL,
    it retrieves the data from the URL using an HTTP request and updates the content to include the data.

    Parameters:
    - resource (dict): A DocumentReference resource as a dictionary.
    - base_url (str): The base URL used for making HTTP requests to resolve the content URLs.
    - query_headers (dict): Additional headers for the HTTP request.

    Returns:
    - dict: The expanded DocumentReference resource with content data fields.

    Errors and Logging:
    - If the Binary retrieval fails (e.g., due to a non-200 status code), an error message is logged containing the status code and provides information about possible solutions for the error.
    - If a 403 status code is encountered, it suggests that the user's scope may be insufficient and provides guidance on checking the scope to ensure it includes 'Binary.Read'.
    - If the HTTP response contains 'WWW-Authenticate' headers, they are logged to provide additional diagnostic information.

    This function handles HTML attachments by converting them to plain text if necessary.
    """

    if resource['resourceType'] == 'OperationOutcome':
        handle_operation_outcomes(resource=resource)
        return resource

    for i, content in enumerate(resource['content']):
        if 'url' in content['attachment']:
            binary_url = content['attachment']['url']
            logger.debug(f'Querying {base_url + "/" + binary_url}')
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

    # Convert HTML to plain text
    html_contents = list(filter(lambda x: x['attachment']['contentType'] == 'text/html', resource['content']))
    converted_htmls = []

    for content in html_contents:
        html_blurb = content['attachment']['data']
        text_blurb = html2text.html2text(html_blurb)
        text_blurb_bytes = text_blurb.encode('utf-8')
        base64_text = base64.b64encode(text_blurb_bytes).decode('utf-8')
        converted_htmls.append({"attachment": {"contentType": "text/plain", "data": base64_text}})

    resource['content'].extend(converted_htmls)

    return resource

def expand_document_references_in_bundle(input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle:
    """
    Expand content attachments of DocumentReference entries within a Bundle.

    This function takes a FHIR Bundle containing DocumentReference resources and expands content attachments into data fields for each entry.

    Parameters:
    - input_bundle (Bundle): The input FHIR Bundle containing DocumentReference entries to be processed.
    - base_url (str): The base URL used for making HTTP requests to resolve content URLs.
    - query_headers (dict, optional): Additional headers for the HTTP requests (default: {}).

    Returns:
    - Bundle: A modified FHIR Bundle with expanded content data or the original input Bundle if an error occurs.
    """
    returned_resources = input_bundle.entry
    output_bundle = deepcopy(input_bundle).dict(exclude_none=True)
    expanded_entries = []

    for entry in returned_resources:
        entry = entry.dict(exclude_none=True) #type: ignore
        resource = entry['resource']
        expanded_resource = expand_document_reference_content(resource, base_url, query_headers)
        if expanded_resource:
            entry['resource'] = expanded_resource
        expanded_entries.append(entry)

    output_bundle['entry'] = expanded_entries
    return Bundle.parse_obj(output_bundle)