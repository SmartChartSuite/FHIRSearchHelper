import base64
import json

import httpx
from fhir.resources.R4B.bundle import Bundle

from fhirsearchhelper.helpers import documenthelper
from fhirsearchhelper.helpers.documenthelper import expand_document_references_in_bundle, expand_single_document_reference_content

transport: httpx.HTTPTransport = httpx.HTTPTransport(retries=5)
client: httpx.Client = httpx.Client(transport=transport)


def test_expand_document_references_no_binary() -> None:
    with open("./tests/resources/DocumentReferencesNoBinary.json", "r") as fopen:
        bundle_data = json.load(fopen)
    dc_bundle = Bundle.model_validate(bundle_data)

    output = expand_document_references_in_bundle(client=client, input_bundle=dc_bundle, base_url="https://hapi.fhir.org/baseR4/")

    assert isinstance(output, Bundle)
    assert output.model_dump(exclude_none=True) == dc_bundle.model_dump(exclude_none=True)


def test_html_binary_is_encoded_once_for_plain_text(monkeypatch) -> None:
    html = "<h1>Hello</h1>"
    encoded_html = base64.b64encode(html.encode("utf-8")).decode("ascii")

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get(self, url: str, headers: dict[str, str]) -> httpx.Response:
            binary_resource = json.dumps({"resourceType": "Binary", "contentType": "text/html", "data": encoded_html})
            request = httpx.Request("GET", url, headers=headers)
            return httpx.Response(200, content=binary_resource.encode("utf-8"), headers={"content-type": "application/fhir+json"}, request=request)

    monkeypatch.setattr(documenthelper.httpx, "Client", FakeClient)
    documenthelper.cached_binary_resources.clear()
    resource = {"resourceType": "DocumentReference", "content": [{"attachment": {"contentType": "text/html", "url": "Binary/1"}}]}

    output = expand_single_document_reference_content(resource, base_url="https://fhir.example", query_headers={})

    assert output is not None
    plain_text_attachment = output["content"][0]["attachment"]
    assert plain_text_attachment["contentType"] == "text/plain"
    decoded_text = base64.b64decode(plain_text_attachment["data"]).decode("utf-8")
    assert "Hello" in decoded_text
    assert "<h1>" not in decoded_text
