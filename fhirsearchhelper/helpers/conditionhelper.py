"""File to handle all operations around Condition Resources"""

import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any

from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType
from requests import Response, Session

from .operationoutcomehelper import handle_operation_outcomes

logger: logging.Logger = logging.getLogger("fhirsearchhelper.conditionhelper")

cached_encounter_resources: dict = {}


def expand_condition_onset(entry_resource: BundleEntryType) -> dict[str, Any] | None:
    """
    Add condition onset date and time information using an Encounter reference.

    This function is designed to enrich a 'Condition' resource by adding onsetDateTime. If the 'Condition' resource already contains 'onsetDateTime', no changes are made.

    Parameters:
    - entry_resource (dict): A Bundle.entry where resourceType is Condition as a dictionary.

    Returns:
    - dict[str, Any] or None: A Bundle.entry with a modified 'Condition' resource dictionary with the 'onsetDateTime' field added or None if an error occurs during the retrieval of the referenced Encounter.

    If the 'Condition' resource references an Encounter, this function makes an HTTP request to fetch the Encounter resource using the provided 'base_url' and 'query_headers'. If successful,
    it extracts the 'start' field from the Encounter's 'period' and adds it as the 'onsetDateTime' in the 'Condition' resource.

    Errors and Logging:
    - If the Encounter retrieval fails (e.g., due to a non-200 status code), an error message is logged containing the status code and provides information about possible solutions for the error.
    - If a 403 status code is encountered, it suggests that the user's scope may be insufficient and provides guidance on checking the scope to ensure it includes 'Encounter.Read'.
    - If the HTTP response contains 'WWW-Authenticate' headers, they are logged to provide additional diagnostic information.
    """

    entry: dict = entry_resource.dict(exclude_none=True)  # type: ignore
    resource: dict = entry["resource"]
    if resource["resourceType"] == "OperationOutcome":
        handle_operation_outcomes(resource=resource)
        return None

    if any(onset_key in resource for onset_key in ["onsetAge", "onsetDateTime", "onsetPeriod", "onsetRange", "onsetString", "recordedDate"]):
        return entry
    if "encounter" in resource and "reference" in resource["encounter"]:
        encounter_ref: str = resource["encounter"]["reference"]
        if g_base_url + "/" + encounter_ref in cached_encounter_resources:
            logger.debug("Found Encounter in cached resources")
            encounter_json: dict = cached_encounter_resources[g_base_url + "/" + encounter_ref]
        else:
            logger.debug(f'Did not find Encounter in cached resources, querying {g_base_url+"/"+encounter_ref}')
            encounter_lookup: Response = g_session.get(f"{g_base_url}/{encounter_ref}", headers=g_query_headers)
            if encounter_lookup.status_code != 200:
                logger.error(f"The Condition Encounter query responded with a status code of {encounter_lookup.status_code}")
                if encounter_lookup.status_code == 403:
                    logger.error("The 403 code typically means your defined scope does not allow for retrieving this resource. Please check your scope to ensure it includes Encounter.Read.")
                    if "WWW-Authenticate" in encounter_lookup.headers:
                        logger.error(encounter_lookup.headers["WWW-Authenticate"])
                return None
            encounter_json = encounter_lookup.json()
            cached_encounter_resources[g_base_url + "/" + encounter_ref] = encounter_json
        if "period" in encounter_json and "start" in encounter_json["period"]:
            resource["onsetDateTime"] = encounter_json["period"]["start"]
        else:
            resource["onsetDateTime"] = "9999-12-31"
    else:
        resource["onsetDateTime"] = "9999-12-31"

    entry["resource"] = resource
    return entry


def expand_condition_onset_in_bundle(session: Session, input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle:
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
    global cached_encounter_resources, g_session, g_base_url, g_query_headers
    g_session: Session = session
    g_base_url: str = base_url
    g_query_headers: dict[str, str] = query_headers

    returned_resources: list[BundleEntryType] = input_bundle.entry
    output_bundle: dict = deepcopy(input_bundle).dict(exclude_none=True)

    with ThreadPoolExecutor() as executor:
        future_to_entry: dict[Future[dict[str, Any] | None], BundleEntryType] = {executor.submit(expand_condition_onset, entry): entry for entry in returned_resources}

        expanded_entries: list[dict[str, Any] | None] = []
        for future in as_completed(future_to_entry):
            entry: dict[str, Any] | None = future.result()
            if entry:
                expanded_entries.append(entry)

    expanded_entries_clean: list[dict[str, Any]] = [entry for entry in expanded_entries if entry]

    if len(cached_encounter_resources.keys()) != 0:
        cached_encounter_resources = {}

    output_bundle["entry"] = expanded_entries_clean
    return Bundle.parse_obj(output_bundle)
