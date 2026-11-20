"""File to perform filtering of returned FHIR resources using output from gap analysis"""

import json
import logging
import re
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote_plus

import fhirpathpy
from fhir.resources.R4B.bundle import Bundle, BundleEntry

from ..models.models import QuerySearchParams

logger: logging.Logger = logging.getLogger("fhirsearchhelper.fhirfilter")


def _base_search_parameter(name: str) -> str:
    return name.split(":", 1)[0]


@cache
def _search_parameter_paths(resource_type: str) -> dict[str, str]:
    with open(f"{Path(__file__).parents[1]}/resources/fhir_r4_search_params.json", "r") as fin:
        definitions = json.load(fin)
    return {name: definition["fhirpath"] for name, definition in definitions.get(resource_type, {}).items() if "fhirpath" in definition}


def _flatten_search_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        flattened: list[str] = []
        if value.get("system") is not None and value.get("code") is not None:
            flattened.append(f"{value['system']}|{value['code']}")
        if value.get("reference") is not None:
            flattened.append(str(value["reference"]))
        for nested in value.values():
            flattened.extend(_flatten_search_values(nested))
        return flattened
    if isinstance(value, list):
        flattened = []
        for nested in value:
            flattened.extend(_flatten_search_values(nested))
        return flattened
    if value is None:
        return []
    return [str(value)]


def _evaluate_search_parameter(resource: Any, resource_type: str, search_parameter: str) -> list[Any]:
    fhirpath = _search_parameter_paths(resource_type).get(search_parameter)
    if not fhirpath:
        return []

    resource_data = resource.model_dump(exclude_none=True)
    try:
        return fhirpathpy.evaluate(resource_data, fhirpath)
    except Exception as exc:  # noqa: BLE001 - fhirpathpy raises generic exceptions for unsupported expressions
        simplified_fhirpath = re.sub(r"\.where\(resolve\(\) is [^)]+\)", "", fhirpath)
        if simplified_fhirpath == fhirpath:
            logger.warning("Unable to evaluate FHIRPath for :not filtering (%s.%s): %s", resource_type, search_parameter, exc)
            return []
        try:
            return fhirpathpy.evaluate(resource_data, simplified_fhirpath)
        except Exception as simplified_exc:  # noqa: BLE001 - fhirpathpy raises generic exceptions for unsupported expressions
            logger.warning("Unable to evaluate simplified FHIRPath for :not filtering (%s.%s): %s", resource_type, search_parameter, simplified_exc)
            return []


def _search_parameter_matches(resource: Any, resource_type: str, search_parameter: str, search_value: str) -> bool:
    expected = unquote_plus(search_value)
    values = _evaluate_search_parameter(resource, resource_type, search_parameter)
    for candidate in values:
        for candidate_value in _flatten_search_values(candidate):
            normalized_candidate = unquote_plus(candidate_value)
            if normalized_candidate == expected or normalized_candidate.endswith(f"/{expected}"):
                return True
    return False


def filter_bundle(input_bundle: Bundle, search_params: QuerySearchParams, gap_analysis_output: list[str]) -> Bundle:
    """Function that takes an input bundle, the original search params, and the output from the gap analysis to filter a Bundle"""

    logger.debug("Filtering Bundle using gap analysis output...")

    if not gap_analysis_output:
        return input_bundle

    returned_resources: list[BundleEntry] | None = input_bundle.entry
    if not returned_resources:
        return input_bundle

    not_filters = [filter_sp for filter_sp in gap_analysis_output if filter_sp.lower().endswith(":not")]
    for filter_sp in not_filters:
        base_search_parameter = _base_search_parameter(filter_sp)
        search_value = search_params.searchParams[filter_sp]
        returned_resources = [
            entry
            for entry in returned_resources
            if not entry.resource or not _search_parameter_matches(entry.resource, search_params.resourceType, base_search_parameter, search_value)
        ]

    gap_analysis_output = [filter_sp for filter_sp in gap_analysis_output if filter_sp not in not_filters]
    filtered_entries: list[BundleEntry] = []
    output_bundle: Bundle = deepcopy(input_bundle)
    if not gap_analysis_output:
        output_bundle.entry = returned_resources
        output_bundle.total = len(returned_resources)
        return output_bundle

    for filter_sp in gap_analysis_output:
        filter_sp_value: str = unquote_plus(str(search_params.searchParams[filter_sp]))
        if "-" in filter_sp:
            filter_sp = filter_sp[0].lower() + "".join(x.capitalize() for x in filter_sp.lower().split("-"))[1:]
        logger.debug("Working on filtering for search parameter %s", filter_sp)
        match filter_sp:
            case "code":
                code_sp_multiple_codes = filter_sp_value.split(",")
                if len(code_sp_multiple_codes) > 1:
                    logger.debug("There are a total of %s codes in the search parameter", len(code_sp_multiple_codes))
                for code_sp_single_code in code_sp_multiple_codes:
                    code_sp_split: list[str] = code_sp_single_code.split("|")
                    if len(code_sp_split) == 2:  # Case when there is a | separator
                        code_sp_system: str = code_sp_split[0]
                        code_sp_code: str = code_sp_split[1]
                    else:
                        code_sp_system = ""
                        code_sp_code = code_sp_split[0]
                    for entry in returned_resources:
                        if not entry.resource:
                            continue
                        resource: Any = cast(Any, entry.resource)
                        if resource.__resource_type__ == "MedicationRequest":
                            if "coding" not in resource.medicationCodeableConcept.model_dump():
                                logger.debug("Code does not have a coding, this MedicationRequest resource does not match")
                                continue
                            if code_sp_system and list(filter(lambda x: x.system == code_sp_system and x.code == code_sp_code, resource.medicationCodeableConcept.coding)):
                                logger.debug("Found MedicationRequest that matched both system and code for code element")
                                filtered_list = [(idx, med) for idx, med in enumerate(resource.medicationCodeableConcept.coding) if med.system == code_sp_system and med.code == code_sp_code]
                                swap_entries = resource.medicationCodeableConcept.coding[filtered_list[0][0]], resource.medicationCodeableConcept.coding[0]
                                resource.medicationCodeableConcept.coding[0], resource.medicationCodeableConcept.coding[filtered_list[0][0]] = swap_entries
                                filtered_entries.append(entry)
                            elif any(coding.code == code_sp_code for coding in resource.medicationCodeableConcept.coding):
                                logger.debug("Found MedicationRequest that matches code (system was not provided in original query)")
                                filtered_list = [(idx, med) for idx, med in enumerate(resource.medicationCodeableConcept.coding) if med.code == code_sp_code]
                                swap_entries = resource.medicationCodeableConcept.coding[filtered_list[0][0]], resource.medicationCodeableConcept.coding[0]
                                resource.medicationCodeableConcept.coding[0], resource.medicationCodeableConcept.coding[filtered_list[0][0]] = swap_entries
                                filtered_entries.append(entry)
                        else:
                            if "coding" not in resource.code.model_dump():
                                logger.debug("Code does not have a coding, this %s resource does not match", resource.__resource_type__)
                                continue
                            if code_sp_system and list(filter(lambda x: x.system == code_sp_system and x.code == code_sp_code, resource.code.coding)):
                                logger.debug("Found resource that matched both system and code for code element")
                                filtered_entries.append(entry)
                            elif any(coding.code == code_sp_code for coding in resource.code.coding):
                                logger.debug("Found resource that matches code (system was not provided in original query)")
                                filtered_entries.append(entry)
            case "category":
                category_sp_split: list[str] = filter_sp_value.split("|")
                if len(category_sp_split) == 2:  # Case when there is a | separator
                    category_sp_system: str = category_sp_split[0]
                    category_sp_code: str = category_sp_split[1]
                else:
                    category_sp_system = ""
                    category_sp_code = category_sp_split[0]
                for entry in returned_resources:
                    if not entry.resource:
                        continue
                    resource: Any = cast(Any, entry.resource)
                    if (category_sp_system and list(filter(lambda x: x.system == category_sp_system and x.code == category_sp_code, resource.category))) or any(coding.code == category_sp_code for coding in resource.category.coding):
                        filtered_entries.append(entry)
            case "clinicalStatus":
                for entry in returned_resources:
                    if entry.model_dump(exclude_none=True)["resource"][filter_sp]["coding"][0]["code"] in filter_sp_value.split(","):
                        filtered_entries.append(entry)
            case _:
                for entry in returned_resources:
                    if entry.model_dump(exclude_none=True)["resource"][filter_sp] == filter_sp_value:
                        filtered_entries.append(entry)

    output_bundle.entry = filtered_entries
    output_bundle.total = len(filtered_entries)

    return output_bundle


def filter_bundle_new(input_bundle: Bundle, search_params: QuerySearchParams, gap_analysis_output: list[str]) -> Bundle:
    """Function that takes an input bundle, the original search params, and the output from the gap analysis to filter a Bundle"""

    logger.debug("Filtering Bundle using gap analysis output...")

    if not gap_analysis_output:
        return input_bundle

    returned_resources: list[BundleEntry] | None = input_bundle.entry
    if not returned_resources:
        return input_bundle
    filtered_entries: list[BundleEntry] = []
    output_bundle: Bundle = deepcopy(input_bundle)

    with open(f"{Path(__file__).parents[1]}/resources/fhir_r4_search_params.json", "r") as fin:
        r4_sp_json = json.load(fin)

    for filter_sp in gap_analysis_output:
        filter_sp_value: str | int | dict = search_params.searchParams[filter_sp]
        if isinstance(filter_sp_value, str):
            filter_sp_value = unquote_plus(filter_sp_value)
        print("Filter sp value", filter_sp_value)
        filter_sp_fhirpath = r4_sp_json[search_params.resourceType][_base_search_parameter(filter_sp)]["fhirpath"]

        for entry in returned_resources:
            if not entry.resource:
                continue
            resource_sp_output = fhirpathpy.evaluate(cast(Any, entry.resource), filter_sp_fhirpath)
            if isinstance(filter_sp_value, str) and "|" in filter_sp_value:
                logger.debug("The filter search parameter value is of type code")
                filter_sp_value = {"system": filter_sp_value.split("|")[0], "code": filter_sp_value.split("|")[1]}
                logger.debug("Updated filter search parameter value to be a dictionary")
                print(filter_sp_value)
            if filter_sp_value in resource_sp_output:  # type: ignore for now bc this a work in progress function
                filtered_entries.append(entry)

    output_bundle.entry = filtered_entries
    output_bundle.total = len(filtered_entries)

    return output_bundle
