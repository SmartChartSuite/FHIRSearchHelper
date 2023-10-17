'''File to handle all operations around Medication-related Resources'''

import logging
from copy import deepcopy

import requests
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType

logger: logging.Logger = logging.getLogger('fhirsearchhelper.medicationhelper')

def expand_medication_references(input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle | None:

    returned_resources: list[BundleEntryType] = input_bundle.entry
    output_bundle: dict = deepcopy(input_bundle).dict(exclude_none=True)
    expanded_entries = []

    for entry in returned_resources:
        entry = entry.dict(exclude_none=True) #type: ignore
        resource = entry['resource']
        if 'medicationReference' in resource:
            med_ref = resource['medicationReference']['reference']
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
            entry['resource'] = resource
            expanded_entries.append(entry)

    output_bundle['entry'] = expanded_entries

    return Bundle.parse_obj(output_bundle)
