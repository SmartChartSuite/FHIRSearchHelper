import json

import httpx
from fhir.resources.R4B.bundle import Bundle

from fhirsearchhelper.helpers.documenthelper import expand_document_references_in_bundle

transport: httpx.HTTPTransport = httpx.HTTPTransport(retries=5)
client: httpx.Client = httpx.Client(transport=transport)


def test_expand_document_references_no_binary() -> None:
    with open("./tests/resources/DocumentReferencesNoBinary.json", "r") as fopen:
        bundle_data = json.load(fopen)
    dc_bundle = Bundle.model_validate(bundle_data)

    output = expand_document_references_in_bundle(client=client, input_bundle=dc_bundle, base_url="https://hapi.fhir.org/baseR4/")

    assert isinstance(output, Bundle)
    assert output.model_dump(exclude_none=True) == dc_bundle.model_dump(exclude_none=True)
