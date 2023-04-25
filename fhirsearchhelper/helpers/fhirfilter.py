'''File to perform filtering of returned FHIR resources using output from gap analysis'''

from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType
from models.models import QuerySearchParams
from copy import deepcopy

def filter_bundle(input_bundle: Bundle, search_params: QuerySearchParams, gap_analysis_output: list[str]) -> Bundle:
    '''Function that takes an input bundle, the original search params, and the output from the gap analysis to filter a Bundle'''

    returned_resources: list[BundleEntryType] = input_bundle.entry
    filtered_entries: list[BundleEntryType] = []
    output_bundle: Bundle = deepcopy(input_bundle)

    for filter_sp in gap_analysis_output:
        filter_sp_value: str | int = search_params.searchParams[filter_sp]
        match filter_sp.lower():
            case 'code':
                code_sp_split: list[str] = filter_sp_value.split('|')
                if len(code_sp_split) == 2: # Case when there is a | separator
                    code_sp_system: str = code_sp_split[0]
                    code_sp_code: str = code_sp_split[1]
                else:
                    code_sp_system = ''
                    code_sp_code = code_sp_split[0]
                for entry in returned_resources:
                    if code_sp_system and list(filter(lambda x: x.system == code_sp_system and x.code == code_sp_code, entry.resource.code)): # type: ignore
                        filtered_entries.append(entry)
                    elif any([coding.code == code_sp_code for coding in entry.resource.code.coding]): # type: ignore
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
            case _:
                for entry in returned_resources:
                    if entry.dict()[filter_sp] == filter_sp_value: # type: ignore
                        filtered_entries.append(entry)

    output_bundle.entry = filtered_entries
    output_bundle.total = len(filtered_entries) # type: ignore

    return output_bundle