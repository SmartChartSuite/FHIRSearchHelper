"""File to handle all operations around Medication-related Resources"""

import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any

from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType
from requests import Response, Session

from .operationoutcomehelper import handle_operation_outcomes

logger: logging.Logger = logging.getLogger("fhirsearchhelper.medicationhelper")

cached_medication_resources: dict = {}


def expand_medication_reference(entry_resource: BundleEntryType) -> dict[str, Any] | None:
    """
    Expand a MedicationReference within a Bundle.entry.resource.MedicationRequest resource to a MedicationCodeableConcept.

    This function takes a Bundle.entry where the entry.resource is of type MedicationRequest, and if it contains a MedicationReference, it expands it into a MedicationCodeableConcept by resolving the reference using an HTTP request.

    Parameters:
    - entry_resource (dict): A Bundle.entry where resourceType is MedicationRequest as a dictionary.

    Returns:
    - dict: The expanded MedicationRequest resource with MedicationCodeableConcept.

    Errors and Logging:
    - If the Medication retrieval fails (e.g., due to a non-200 status code), an error message is logged containing the status code and provides information about possible solutions for the error.
    - If a 403 status code is encountered, it suggests that the user's scope may be insufficient and provides guidance on checking the scope to ensure it includes 'Medication.Read'.
    - If the HTTP response contains 'WWW-Authenticate' headers, they are logged to provide additional diagnostic information.

    """

    entry: dict[str, Any] = entry_resource.dict(exclude_none=True)  # type: ignore
    resource: dict[str, Any] = entry["resource"]
    if resource["resourceType"] == "OperationOutcome":
        handle_operation_outcomes(resource=resource)
        return resource

    if "medicationReference" in resource:
        med_ref: str = resource["medicationReference"]["reference"]
        if g_base_url + "/" + med_ref in cached_medication_resources:
            logger.debug("Found Medication in cached resources")
            med_code_concept: dict[str, list[dict]] = cached_medication_resources[g_base_url + "/" + med_ref]["code"]
        else:
            logger.debug(f'Did not find Medication in cached resources, querying {g_base_url+"/"+med_ref}')
            med_lookup: Response = g_session.get(f"{g_base_url}/{med_ref}", headers=g_query_headers)
            if med_lookup.status_code != 200:
                logger.error(f"The MedicationRequest Medication query responded with a status code of {med_lookup.status_code}")
                if med_lookup.status_code == 403:
                    logger.error("The 403 code typically means your defined scope does not allow for retrieving this resource. Please check your scope to ensure it includes Medication.Read.")
                    if "WWW-Authenticate" in med_lookup.headers:
                        logger.error(med_lookup.headers["WWW-Authenticate"])
                return None
            cached_medication_resources[g_base_url + "/" + med_ref] = med_lookup.json()
            med_code_concept = med_lookup.json()["code"]
        resource["medicationCodeableConcept"] = med_code_concept
        del resource["medicationReference"]
        entry["resource"] = resource

    return entry


def expand_medication_references_in_bundle(session: Session, input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle:
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

    global cached_medication_resources, g_session, g_base_url, g_query_headers
    g_session, g_base_url, g_query_headers = session, base_url, query_headers

    returned_resources: list[BundleEntryType] = input_bundle.entry
    output_bundle: dict = deepcopy(input_bundle).dict(exclude_none=True)

    with ThreadPoolExecutor() as executor:
        future_to_entry: dict[Future[dict[str, Any] | None], BundleEntryType] = {executor.submit(expand_medication_reference, entry): entry for entry in returned_resources}

        expanded_entries: list[dict[str, Any] | None] = []
        for future in as_completed(future_to_entry):
            entry: dict[str, Any] | None = future.result()
            if entry:
                expanded_entries.append(entry)

    expanded_entries_clean: list[dict[str, Any]] = [entry for entry in expanded_entries if entry]

    if len(cached_medication_resources.keys()) != 0:
        cached_medication_resources = {}

    output_bundle["entry"] = expanded_entries_clean
    return Bundle.parse_obj(output_bundle)
