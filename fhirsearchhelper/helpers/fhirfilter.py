'''File to perform filtering of returned FHIR resources using output from gap analysis'''

import json
import logging
from copy import deepcopy
from pathlib import Path

import fhirpathpy
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType

from ..models.models import QuerySearchParams

logger: logging.Logger = logging.getLogger('fhirsearchhelper.fhirfilter')


def filter_bundle(input_bundle: Bundle, search_params: QuerySearchParams, gap_analysis_output: list[str]) -> Bundle:
    '''Function that takes an input bundle, the original search params, and the output from the gap analysis to filter a Bundle'''

    logger.debug('Filtering Bundle using gap analysis output...')

    if not gap_analysis_output:
        return input_bundle

    returned_resources: list[BundleEntryType] = input_bundle.entry
    filtered_entries: list[BundleEntryType] = []
    output_bundle: Bundle = deepcopy(input_bundle)

    for filter_sp in gap_analysis_output:
        filter_sp_value: str | int = search_params.searchParams[filter_sp]
        if '-'  in filter_sp:
            filter_sp = filter_sp[0].lower() + "".join(x.capitalize() for x in filter_sp.lower().split("-"))[1:]
        logger.debug(f'Working on filtering for search parameter {filter_sp}')
        match filter_sp:
            case 'code':
                code_sp_split: list[str] = filter_sp_value.split('%7C')
                if len(code_sp_split) == 2: # Case when there is a | separator
                    logger.debug('Code search parameter value has a |')
                    code_sp_system: str = code_sp_split[0]
                    code_sp_code: str = code_sp_split[1]
                else:
                    logger.debug('Code search parameter contains just the code')
                    code_sp_system = ''
                    code_sp_code = code_sp_split[0]
                for entry in returned_resources:
                    if entry.resource.resource_type == 'MedicationRequest': #type: ignore
                        if code_sp_system and list(filter(lambda x: x.system == code_sp_system and x.code == code_sp_code, entry.resource.medicationCodeableConcept.coding)): # type: ignore
                            logger.debug('Found MedicationRequest that matched both system and code for code element')
                            filtered_entries.append(entry)
                        elif any([coding.code == code_sp_code for coding in entry.resource.medicationCodeableConcept.coding]): # type: ignore
                            logger.debug('Found MedicationRequest that matches code (system was not provided in original query)')
                            filtered_entries.append(entry)
                    else:
                        if code_sp_system and list(filter(lambda x: x.system == code_sp_system and x.code == code_sp_code, entry.resource.code.coding)): # type: ignore
                            logger.debug('Found resource that matched both system and code for code element')
                            filtered_entries.append(entry)
                        elif any([coding.code == code_sp_code for coding in entry.resource.code.coding]): # type: ignore
                            logger.debug('Found resource that matches code (system was not provided in original query)')
                            filtered_entries.append(entry)
            case 'category':
                category_sp_split: list[str] = filter_sp_value.split('|')
                if len(category_sp_split) == 2: # Case when there is a | separator
                    category_sp_system: str = category_sp_split[0]
                    category_sp_code: str = category_sp_split[1]
                else:
                    category_sp_system = ''
                    category_sp_code = category_sp_split[0]
                for entry in returned_resources:
                    if category_sp_system and list(filter(lambda x: x.system == category_sp_system and x.code == category_sp_code, entry.resource.category)): # type: ignore
                        filtered_entries.append(entry)
                    elif any([coding.code == category_sp_code for coding in entry.resource.category.coding]): # type: ignore
                        filtered_entries.append(entry)
            case 'clinicalStatus':
                for entry in returned_resources:
                    if entry.dict(exclude_none=True)['resource'][filter_sp]['coding'][0]['code'] in filter_sp_value.split(','): # type: ignore
                        filtered_entries.append(entry)
            case _:
                for entry in returned_resources:
                    if entry.dict(exclude_none=True)['resource'][filter_sp] == filter_sp_value: # type: ignore
                        filtered_entries.append(entry)

    output_bundle.entry = filtered_entries
    output_bundle.total = len(filtered_entries) # type: ignore

    return output_bundle


def filter_bundle_new(input_bundle: Bundle, search_params: QuerySearchParams, gap_analysis_output: list[str]) -> Bundle:
    '''Function that takes an input bundle, the original search params, and the output from the gap analysis to filter a Bundle'''

    logger.debug('Filtering Bundle using gap analysis output...')

    if not gap_analysis_output:
        return input_bundle

    returned_resources: list[BundleEntryType] = input_bundle.entry
    filtered_entries: list[BundleEntryType] = []
    output_bundle: Bundle = deepcopy(input_bundle)

    with open(f'{Path(__file__).parents[1]}/resources/fhir_r4_search_params.json', 'r') as fin:
        r4_sp_json = json.load(fin)

    for filter_sp in gap_analysis_output:
        filter_sp_value: str | int | dict = search_params.searchParams[filter_sp]
        print('Filter sp value', filter_sp_value)
        filter_sp_fhirpath = r4_sp_json[search_params.resourceType][filter_sp]['fhirpath']

        for entry in returned_resources:
            resource_sp_output = fhirpathpy.evaluate(entry.resource, filter_sp_fhirpath) #type: ignore
            if isinstance(filter_sp_value, str) and '%7C' in filter_sp_value:
                logger.debug('The filter search parameter value is of type code')
                filter_sp_value = {'system': filter_sp_value.split('%7C')[0], 'code': filter_sp_value.split('%7C')[1]}
                logger.debug('Updated filter search parameter value to be a dictionary')
                print(filter_sp_value)
            if filter_sp_value in resource_sp_output:
                filtered_entries.append(entry)

    output_bundle.entry = filtered_entries
    output_bundle.total = len(filtered_entries) # type: ignore

    return output_bundle