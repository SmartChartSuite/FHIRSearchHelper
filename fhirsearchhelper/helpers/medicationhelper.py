'''File to handle all operations around Medication-related Resources'''

import logging
from copy import deepcopy
from typing import Any

import requests
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType

from .operationoutcomehelper import handle_operation_outcomes

logger: logging.Logger = logging.getLogger('fhirsearchhelper.medicationhelper')

def expand_medication_reference(resource: dict, base_url: str, query_headers: dict) -> dict[str, Any] | None:
    """
    Expand a MedicationReference within a MedicationRequest resource to a MedicationCodeableConcept.

    This function takes a MedicationRequest resource, and if it contains a MedicationReference, it expands it into a MedicationCodeableConcept by resolving the reference using an HTTP request.

    Parameters:
    - resource (dict): A MedicationRequest resource as a dictionary.
    - base_url (str): The base URL used for making HTTP requests to resolve the MedicationReference.
    - query_headers (dict): Additional headers for the HTTP request.

    Returns:
    - dict: The expanded MedicationRequest resource with MedicationCodeableConcept.

    Errors and Logging:
    - If the Medication retrieval fails (e.g., due to a non-200 status code), an error message is logged containing the status code and provides information about possible solutions for the error.
    - If a 403 status code is encountered, it suggests that the user's scope may be insufficient and provides guidance on checking the scope to ensure it includes 'Medication.Read'.
    - If the HTTP response contains 'WWW-Authenticate' headers, they are logged to provide additional diagnostic information.

    """

    if 'medicationReference' in resource:
        med_ref = resource['medicationReference']['reference']
        logger.debug(f'Querying {base_url+"/"+med_ref}')
        med_lookup = requests.get(f'{base_url}/{med_ref}', headers=query_headers)
        if med_lookup.status_code != 200:
            logger.error(f'The MedicationRequest Medication query responded with a status code of {med_lookup.status_code}')
            if med_lookup.status_code == 403:
                logger.error('The 403 code typically means your defined scope does not allow for retrieving this resource. Please check your scope to ensure it includes Medication.Read.')
                if 'WWW-Authenticate' in med_lookup.headers:
                    logger.error(med_lookup.headers['WWW-Authenticate'])
            return None
        med_code_concept = med_lookup.json()['code']
        resource['medicationCodeableConcept'] = med_code_concept
        del resource['medicationReference']

    return resource


def expand_medication_references_in_bundle(input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle:
    """
    Expand MedicationReferences into MedicationCodeableConcepts for all MedicationRequest entries in a Bundle.

    This function takes a FHIR Bundle containing MedicationRequest resources and expands MedicationReferences into MedicationCodeableConcepts for each entry.

    Parameters:
    - input_bundle (Bundle): The input FHIR Bundle containing MedicationRequest resources to be processed.
    - base_url (str): The base URL used for making HTTP requests to resolve MedicationReferences.
    - query_headers (dict, optional): Additional headers for the HTTP requests (default: {}).

    Returns:
    - Bundle: A modified FHIR Bundle with expanded MedicationReferences or the input Bundle if an error ocurred during expansion.

    The function creates a new Bundle, leaving the original input Bundle unchanged.
    """

    returned_resources: list[BundleEntryType] = input_bundle.entry
    output_bundle = deepcopy(input_bundle).dict(exclude_none=True)
    expanded_entries = []

    for entry in returned_resources:
        entry: dict[str, Any] = entry.dict(exclude_none=True) #type: ignore
        resource: dict[str, Any] = entry['resource']
        if resource['resourceType'] == 'OperationOutcome':
            handle_operation_outcomes(resource=resource)
            continue
        expanded_resource: dict[str, Any] | None = expand_medication_reference(resource, base_url, query_headers)
        if expanded_resource:
            entry['resource'] = expanded_resource
        expanded_entries.append(entry)

    output_bundle['entry'] = expanded_entries
    return Bundle.parse_obj(output_bundle)
