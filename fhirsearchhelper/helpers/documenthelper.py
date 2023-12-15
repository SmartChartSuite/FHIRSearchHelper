"""File to handle all operations around Medication-related Resources"""

import base64
import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any

import html2text
from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.fhirtypes import BundleEntryType
from requests import Response, Session
from requests.exceptions import JSONDecodeError

from .operationoutcomehelper import handle_operation_outcomes

logger: logging.Logger = logging.getLogger("fhirsearchhelper.documenthelper")

cached_binary_resources: dict = {}


def expand_document_reference_content(entry_resource: dict) -> dict | None:
    """
    Expand content attachments of a DocumentReference resource into data fields.

    This function takes a Bunlde.entry where the entry.resource is of type DocumentReference and, for each content attachment that has a URL,
    it retrieves the data from the URL using an HTTP request and updates the content to include the data.

    Parameters:
    - entry_resource (dict): A Bundle.entry where resourceType is DocumentReference resource as a dictionary.

    Returns:
    - dict: The expanded DocumentReference resource with content data fields.

    Errors and Logging:
    - If the Binary retrieval fails (e.g., due to a non-200 status code), an error message is logged containing the status code and provides information about possible solutions for the error.
    - If a 403 status code is encountered, it suggests that the user's scope may be insufficient and provides guidance on checking the scope to ensure it includes 'Binary.Read'.
    - If the HTTP response contains 'WWW-Authenticate' headers, they are logged to provide additional diagnostic information.

    This function handles HTML attachments by converting them to plain text if necessary.
    """

    entry: dict[str, Any] = entry_resource.dict(exclude_none=True)  # type: ignore
    resource: dict[str, Any] = entry["resource"]

    if resource["resourceType"] == "OperationOutcome":
        handle_operation_outcomes(resource=resource)
        return resource

    for i, content in enumerate(resource["content"]):
        if "url" in content["attachment"]:
            binary_url: str = content["attachment"]["url"]
            if g_base_url + "/" + binary_url in cached_binary_resources:
                logger.debug("Found Binary in cached resources")
                content_data: str = cached_binary_resources[g_base_url + "/" + binary_url]
            else:
                logger.debug(f'Did not find Binary in cached resources, querying {g_base_url + "/" + binary_url}')
                binary_url_lookup: Response = g_session.get(f"{g_base_url}/{binary_url}", headers=g_query_headers)

                if binary_url_lookup.status_code != 200:
                    logger.error(f"The query responded with a status code of {binary_url_lookup.status_code}")
                    if binary_url_lookup.status_code == 403:
                        logger.error("The 403 code typically means your defined scope does not allow for retrieving this resource. Please check your scope to ensure it includes Binary.Read.")
                        if "WWW-Authenticate" in binary_url_lookup.headers:
                            logger.error(binary_url_lookup.headers["WWW-Authenticate"])
                    if binary_url_lookup.status_code == 400 and "json" in binary_url_lookup.headers["content-type"]:
                        logger.error(binary_url_lookup.json())
                try:
                    if binary_url_lookup.status_code == 200 and "json" in binary_url_lookup.headers["content-type"]:
                        content_data = binary_url_lookup.json()["data"]
                    elif binary_url_lookup.status_code == 200:
                        content_data = binary_url_lookup.text
                    else:
                        logger.warning("Skipping DocumentReference since Binary resource could not be retrieved")
                        return None
                except JSONDecodeError:
                    logger.warning("Skipping DocumentReference since Binary resource could not be retrieved")
                    logger.warning(f"Response code: {binary_url_lookup.status_code}")
                    logger.warning(f"Response text: {binary_url_lookup.content}")
                    logger.warning(f"Response headers: {binary_url_lookup.headers}")
                    return None
                cached_binary_resources[g_base_url + "/" + binary_url] = content_data

            resource["content"][i]["attachment"]["data"] = content_data
            del resource["content"][i]["attachment"]["url"]

    # Convert HTML to plain text
    html_contents = list(filter(lambda x: x["attachment"]["contentType"] == "text/html", resource["content"]))
    converted_htmls: list = []

    for content in html_contents:
        html_blurb: str = content["attachment"]["data"]
        text_maker = html2text.HTML2Text()
        text_maker.ignore_images = True
        text_blurb: str = text_maker.handle(html_blurb)
        text_blurb_bytes: bytes = text_blurb.encode("utf-8")
        base64_text: str = base64.b64encode(text_blurb_bytes).decode("utf-8")
        converted_htmls.append({"attachment": {"contentType": "text/plain", "data": base64_text}})

    resource["content"].extend(converted_htmls)

    plain_text_content: list[tuple[int, Any]] = [(idx, content) for idx, content in enumerate(resource["content"]) if content["attachment"]["contentType"] == "text/plain"]

    swap_contents: tuple = resource["content"][plain_text_content[0][0]], resource["content"][0]

    resource["content"][0], resource["content"][plain_text_content[0][0]] = swap_contents

    entry["resource"] = resource

    return entry


def expand_document_references_in_bundle(session: Session, input_bundle: Bundle, base_url: str, query_headers: dict = {}) -> Bundle:
    """
    Expand content attachments of DocumentReference entries within a Bundle.

    This function takes a FHIR Bundle containing DocumentReference resources and expands content attachments into data fields for each entry.

    Parameters:
    - input_bundle (Bundle): The input FHIR Bundle containing DocumentReference entries to be processed.
    - base_url (str): The base URL used for making HTTP requests to resolve content URLs.
    - query_headers (dict, optional): Additional headers for the HTTP requests (default: {}).

    Returns:
    - Bundle: A modified FHIR Bundle with expanded content data or the original input Bundle if an error occurs.
    """

    global cached_binary_resources, g_session, g_base_url, g_query_headers
    g_session, g_base_url, g_query_headers = session, base_url, query_headers

    returned_resources: list[BundleEntryType] = input_bundle.entry
    output_bundle: dict = deepcopy(input_bundle).dict(exclude_none=True)

    with ThreadPoolExecutor() as executor:
        future_to_entry: dict[Future[dict[str, Any] | None], BundleEntryType] = {executor.submit(expand_document_reference_content, entry): entry for entry in returned_resources}

        expanded_entries: list = []
        for future in as_completed(future_to_entry):
            entry: dict[str, Any] | None = future.result()
            if entry:
                expanded_entries.append(entry)

    expanded_entries_clean: list[dict[str, Any]] = [entry for entry in expanded_entries if entry]

    if len(cached_binary_resources.keys()) != 0:
        cached_binary_resources = {}

    output_bundle["entry"] = expanded_entries_clean
    return Bundle.parse_obj(output_bundle)
