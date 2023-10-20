'''File to handle all operations around Condition Resources'''

import logging
from copy import deepcopy
from typing import Any

import requests
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType

from .operationoutcomehelper import handle_operation_outcomes

logger: logging.Logger = logging.getLogger('fhirsearchhelper.conditionhelper')

def expand_condition_onset(condition: dict, base_url: str, query_headers: dict = {}) -> dict[str, Any] | None:
    """
    Add condition onset date and time information using an Encounter reference.

    This function is designed to enrich a 'Condition' resource by adding onsetDateTime. If the 'Condition' resource already contains 'onsetDateTime', no changes are made.

    Parameters:
    - condition (dict): A 'Condition' resource as a dictionary.
    - base_url (str): The base URL used for making HTTP requests to resolve the Encounter reference.
    - query_headers (dict, optional): Additional headers for the HTTP request, such as a previously received Bearer token in an OAuth 2.0 workflow (default: {}).

    Returns:
    - dict[str, Any] or None: A modified 'Condition' resource dictionary with the 'onsetDateTime' field added or None if an error occurs during the retrieval of the referenced Encounter.

    If the 'Condition' resource references an Encounter, this function makes an HTTP request to fetch the Encounter resource using the provided 'base_url' and 'query_headers'. If successful,
    it extracts the 'start' field from the Encounter's 'period' and adds it as the 'onsetDateTime' in the 'Condition' resource.

    Errors and Logging:
    - If the Encounter retrieval fails (e.g., due to a non-200 status code), an error message is logged containing the status code and provides information about possible solutions for the error.
    - If a 403 status code is encountered, it suggests that the user's scope may be insufficient and provides guidance on checking the scope to ensure it includes 'Encounter.Read'.
    - If the HTTP response contains 'WWW-Authenticate' headers, they are logged to provide additional diagnostic information.
    """

    if 'onsetDateTime' in condition:
        return condition
    if 'encounter' in condition and 'reference' in condition['encounter']:
        encounter_ref = condition['encounter']['reference']
        logger.debug(f'Querying {base_url+"/"+encounter_ref}')
        encounter_lookup = requests.get(f'{base_url}/{encounter_ref}', headers=query_headers)
        if encounter_lookup.status_code != 200:
            logger.error(f'The Condition Encounter query responded with a status code of {encounter_lookup.status_code}')
            if encounter_lookup.status_code == 403:
                logger.error('The 403 code typically means your defined scope does not allow for retrieving this resource. Please check your scope to ensure it includes Encounter.Read.')
                if 'WWW-Authenticate' in encounter_lookup.headers:
                    logger.error(encounter_lookup.headers['WWW-Authenticate'])
            return None
        encounter_json = encounter_lookup.json()
        if 'period' in encounter_json and 'start' in encounter_json['period']:
            condition['onsetDateTime'] = encounter_json['period']['start']
    return condition


def expand_condition_onset_in_bundle(input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle:
    """
    Expand and modify resources within a FHIR Bundle by adding Condition.onsetDateTime using referenced Encounter in Condition.encounter.

    This function takes a FHIR Bundle (`input_bundle`) and iterates through its resources. For each resource of type 'Condition',
    it adds Condition.onset using Condition.encounter.reference.resolve().period.start.

    Parameters:
    - input_bundle (Bundle): The input FHIR Bundle containing resources to be processed.
    - base_url (str): The base URL to be used for resolving references within the resources.
    - query_headers (dict, optional): Additional headers to include in HTTP requests when resolving references, such as a previously received Bearer token in an OAuth 2.0 workflow (default: {}).

    Returns:
    - Bundle: A modified FHIR Bundle with resources expanded to include Condition.onsetDateTime, or the original input Bundle if any errors occurred when trying to GET the Encounters.
    """

    returned_resources: list[BundleEntryType] = input_bundle.entry
    output_bundle: dict = deepcopy(input_bundle).dict(exclude_none=True)
    expanded_entries = []

    for entry in returned_resources:
        entry = entry.dict(exclude_none=True) #type: ignore
        resource = entry['resource']
        if resource['resourceType'] == 'OperationOutcome':
            handle_operation_outcomes(resource=resource)
            continue
        expanded_condition: dict[str, Any] | None = expand_condition_onset(condition=resource, base_url=base_url, query_headers=query_headers)
        if expanded_condition:
            entry['resource'] = expanded_condition
        expanded_entries.append(entry)

    output_bundle['entry'] = expanded_entries

    return Bundle.parse_obj(output_bundle)
