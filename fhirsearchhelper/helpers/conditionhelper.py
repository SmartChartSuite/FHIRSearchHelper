'''File to handle all operations around Condition Resources'''

import logging
from copy import deepcopy

import requests
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType

logger: logging.Logger = logging.getLogger('fhirsearchhelper.conditionhelper')

def expand_condition_onset_with_encounter(input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle | None:

    returned_resources: list[BundleEntryType] = input_bundle.entry
    output_bundle: dict = deepcopy(input_bundle).dict(exclude_none=True)
    expanded_entries = []

    for entry in returned_resources:
        entry = entry.dict(exclude_none=True) #type: ignore
        resource = entry['resource']
        if 'onsetDateTime' in resource:
            expanded_entries.append(entry)
            continue
        if 'encounter' in resource and 'reference' in resource['encounter']:
            encounter_ref = resource['encounter']['reference']
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
                resource['onsetDateTime'] = encounter_json['period']['start']
                entry['resource'] = resource
        expanded_entries.append(entry)

    output_bundle['entry'] = expanded_entries

    return Bundle.parse_obj(output_bundle)
