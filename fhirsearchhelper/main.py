"""Main file for entrypoint to package"""

import json
import logging
import re
from typing import Any, cast
from urllib.parse import unquote_plus

import httpx
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.capabilitystatement import CapabilityStatement
from fhir.resources.R4B.operationoutcome import OperationOutcome

from .helpers.capabilitystatement import get_supported_search_params, load_capability_statement
from .helpers.conditionhelper import expand_condition_onset_in_bundle
from .helpers.documenthelper import expand_document_references_in_bundle
from .helpers.fhirfilter import filter_bundle
from .helpers.gapanalysis import run_gap_analysis
from .helpers.medicationhelper import expand_medication_references_in_bundle
from .models.models import CustomFormatter, QuerySearchParams, SupportedSearchParams

logger: logging.Logger = logging.getLogger("fhirsearchhelper")
logger.setLevel(logging.INFO)
ch: logging.StreamHandler = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)


def _parse_query_parameters(query_string: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    search_params_dict: dict[str, str] = {}
    search_params_list: list[tuple[str, str]] = []
    for parameter in query_string.split("&"):
        raw_name, separator, raw_value = parameter.partition("=")
        if not raw_name:
            continue
        name = unquote_plus(raw_name)
        value = unquote_plus(raw_value) if separator else ""
        search_params_list.append((raw_name, raw_value))
        search_params_dict[name] = value
    return search_params_dict, search_params_list


def _build_query_string(search_params: QuerySearchParams, gap_output: list[str]) -> str:
    if search_params.searchParamsList is None:
        search_params_list = list(search_params.searchParams.items())
    else:
        search_params_list = search_params.searchParamsList

    new_query_params_str = "&".join([f"{key}={value}" for key, value in search_params_list if unquote_plus(key) not in gap_output])
    if new_query_params_str:
        return f"{search_params.resourceType}?{new_query_params_str}"
    return search_params.resourceType


def run_fhir_query(
    base_url: str | None = None,
    query_headers: dict[str, str] | None = None,
    search_params: QuerySearchParams | None = None,
    query: str | None = None,
    capability_statement_file: str | None = None,
    capability_statement_url: str | None = None,
    debug: bool = False,
) -> Bundle | OperationOutcome | None:
    """
    Entry function to run FHIR query using a CapabilityStatement and returning filtered resources
    WARNING: There is currently not a way to use a CapabilityStatement out of the box. See README.md of source for details.
    """

    if debug:
        logger.info("Logging level is being set to DEBUG")
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        logger.addHandler(ch)

    # Error handling
    if not base_url and not search_params and not query:
        raise ValueError("You must provide either a base_url and a dictionary of search parameters or the full query string in the form of <baseUrl>/<resourceType>?<param1>=<value1>&...")

    transport: httpx.HTTPTransport = httpx.HTTPTransport(retries=5)
    client: httpx.Client = httpx.Client(transport=transport)

    cap_state: CapabilityStatement = load_capability_statement(client=client, url=capability_statement_url, file_path=capability_statement_file)
    supported_search_params: list[SupportedSearchParams] = get_supported_search_params(cap_state)

    pretty_supported_search_params: dict[str, list[str]] = {
        resource_params["resourceType"]: [item["name"] for item in resource_params["searchParams"]] for resource_params in [item.model_dump(exclude_none=True) for item in supported_search_params]
    }

    logger.debug(f"Supported search parameters for this server are: {pretty_supported_search_params}")

    if query:
        url_res, q_search_params = query.split("?")
        if url_res.split("/")[-1] not in pretty_supported_search_params:
            logger.error(f"Resource {url_res.split('/')[-1]} is not supported for searching, returning empty Bundle")
            return Bundle.model_validate({"type": "searchset", "total": 0, "link": [{"relation": "self", "url": url_res}]})
        if not q_search_params:
            logger.error("No search params, Epic does not support pulling all resources of a given type with no search parameters. Please refine your query.")
            new_query_response: httpx.Response = client.get(f"{url_res}", headers=query_headers)
            if new_query_response.status_code == 403:
                logger.error(f"The query responded with a status code of {new_query_response.status_code}")
                if "WWW-Authenticate" in new_query_response.headers:
                    logger.error(f"WWW-Authenticate Error: {new_query_response.headers['WWW-Authenticate']}")
                    OO_body = {
                        "resourceType": "OperationOutcome",
                        "issue": [{"severity": "error", "code": "processing", "diagnostics": f"WWW-Authenticate Error: {new_query_response.headers['WWW-Authenticate']}"}],
                    }
                else:
                    OO_body: dict = {
                        "resourceType": "OperationOutcome",
                        "issue": [{"severity": "error", "code": "processing", "diagnostics": f"The query responded with a status code of {new_query_response.status_code}"}],
                    }
                return OperationOutcome(**OO_body)
            elif new_query_response.status_code == 400:
                return OperationOutcome(**new_query_response.json())
            else:
                return None

        base_url = "/".join(url_res.split("/")[:-1])
        q_resource_type = url_res.split("/")[-1]
        search_params_dict, search_params_list = _parse_query_parameters(q_search_params)
        new_search_params: QuerySearchParams = QuerySearchParams(resourceType=q_resource_type, searchParams=search_params_dict, searchParamsList=search_params_list)
    else:
        assert search_params
        new_search_params = search_params

    logger.info(f"Search parameters for this request are: {new_search_params}")

    gap_output: list[str] = run_gap_analysis(supported_search_params=supported_search_params, query_search_params=new_search_params)

    logger.debug(f"Gap output from these two sets of search parameters is: {gap_output}")

    new_query_string: str = _build_query_string(search_params=new_search_params, gap_output=gap_output)

    logger.debug(f"New query string is {new_query_string}")

    assert base_url
    assert query_headers
    logger.info(f"Making request to {base_url}/{new_query_string}")
    new_query_response = client.get(f"{base_url}/{new_query_string}", headers=query_headers)
    if new_query_response.status_code == 400:
        logger.warning(
            "The query responded with a status code of 400 Bad Request. Most likely this is due to using an incorrect codesystem when searching a code on a resource. "
            "For example, searching CPT or HCPCS codes (Procedure codes) on an Observation. This will return an empty Bundle, but make sure to modify your queries to "
            "only search appropriate codes for the type of resource."
        )
        return Bundle.model_validate({"type": "searchset", "total": 0, "link": [{"relation": "self", "url": f"{base_url}/{new_query_string}"}]})
    if new_query_response.status_code != 200:
        logger.error(f"The query responded with a status code of {new_query_response.status_code}")
        if "WWW-Authenticate" in new_query_response.headers:
            logger.error(f"WWW-Authenticate Error: {new_query_response.headers['WWW-Authenticate']}")
            return OperationOutcome.model_validate(
                {
                    "resourceType": "OperationOutcome",
                    "issue": [{"severity": "error", "code": "processing", "diagnostics": f"WWW-Authenticate Error: {new_query_response.headers['WWW-Authenticate']}"}],
                }
            )
        try:
            return new_query_response.json()
        except json.JSONDecodeError:
            if "html" in new_query_response.headers["Content-Type"]:
                logger.error("Error caused HTML response")
                title_match: re.Match[str] | None = re.search(r"<title>(.*?)</title>", new_query_response.text)
                if title_match:
                    title_content = title_match.group(1)  # Extract the content within the title tags
                    logger.error(f"Response error from query: {title_content}")
                    return OperationOutcome.model_validate({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "processing", "diagnostics": "From Epic: " + title_content}]})
            logger.error("Unable to parse response as JSON body")
            return OperationOutcome.model_validate(
                {
                    "resourceType": "OperationOutcome",
                    "issue": [{"severity": "error", "code": "processing", "diagnostics": "Unable to parse response as JSON or HTML with a title"}],
                }
            )

    new_query_response_json: dict = new_query_response.json()

    try:
        resource = new_query_response_json["entry"][0]["resource"]
        if resource["resourceType"] == "Patient" and "address" in resource:
            # Handling for empty lines in Patient.address
            new_addresses: list[dict] = []
            for address in resource["address"]:
                address["line"] = [line for line in address["line"] if line]
                new_addresses.append(address)
            resource["address"] = new_addresses
    except (IndexError, KeyError):
        pass

    new_query_response_bundle: Bundle = Bundle.model_validate(new_query_response_json)

    if not new_query_response_bundle.entry:
        return new_query_response_bundle

    resource_entries = [entry for entry in new_query_response_bundle.entry if entry.resource]
    return_resource_types = [cast(Any, entry.resource).__resource_type__.lower() for entry in resource_entries]

    if "operationoutcome" in return_resource_types:
        operation_outcomes = [
            cast(OperationOutcome, entry.resource)
            for entry in resource_entries
            if cast(Any, entry.resource).__resource_type__ == "OperationOutcome"
        ]
        if all(item == "operationoutcome" for item in return_resource_types):
            logger.warning("There was only OperationOutcomes in the return Bundle. Bundle.entry will be empty. See below for collected diagnostics or details strings:")
            collected_log_strings = list(
                {
                    issue.diagnostics if issue.diagnostics else issue.details.text if issue.details and issue.details.text else None
                    for outcome in operation_outcomes
                    for issue in outcome.issue
                }
            )
            logger.warning(collected_log_strings)
            new_query_response_bundle.entry = []
        else:
            logger.warning("There was at least one OperationOutcome in the return Bundle. See below for collected diagnostics or details strings:")
            collected_log_strings = list(
                {
                    issue.diagnostics if issue.diagnostics else issue.details.text if issue.details and issue.details.text else None
                    for outcome in operation_outcomes
                    for issue in outcome.issue
                }
            )
            logger.warning(collected_log_strings)
            new_query_response_bundle.entry = [
                entry for entry in resource_entries if cast(Any, entry.resource).__resource_type__ != "OperationOutcome"
            ]

    # This happens before since its searching on code which is completed by this expansion
    if "MedicationRequest" in new_query_string:
        logger.info("Resources are of type MedicationRequest, proceeding to expand MedicationReferences")
        new_query_response_bundle = expand_medication_references_in_bundle(client=client, input_bundle=new_query_response_bundle, base_url=base_url, query_headers=query_headers)

    logger.debug(f"Size of bundle before filtering is {new_query_response_bundle.total} resources")
    filtered_bundle: Bundle = filter_bundle(input_bundle=new_query_response_bundle, search_params=new_search_params, gap_analysis_output=gap_output)
    logger.info(f"Size of bundle after filtering is {filtered_bundle.total} resources")

    output_bundle = filtered_bundle

    if "DocumentReference" in new_query_string:
        logger.info("Resources are of type DocumentReference, proceeding to expand DocumentReferences")
        output_bundle = expand_document_references_in_bundle(client=client, input_bundle=filtered_bundle, base_url=base_url, query_headers=query_headers)
    elif "Condition" in new_query_string:
        logger.info("Resources are of type Condition, checking if any are Encounter Diagnoses...")
        if "encounter-diagnosis" in [category.coding[0].code for entry in filtered_bundle.entry for category in entry.resource.category]:  # type: ignore
            logger.info("Found Condition resources with category Encounter Diagnosis, proceeding to extract Encounter.period.start as Condition.onsetDateTime")
            output_bundle = expand_condition_onset_in_bundle(client=client, input_bundle=filtered_bundle, base_url=base_url, query_headers=query_headers)

    return output_bundle
