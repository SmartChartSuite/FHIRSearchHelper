from fhir.resources.R4B.bundle import Bundle
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from fhirsearchhelper.helpers.documenthelper import expand_document_references_in_bundle

session: Session = Session()
retries: Retry = Retry(total=5, allowed_methods={"GET", "POST", "PUT", "DELETE"}, status_forcelist=[500])
session.mount("https://", HTTPAdapter(max_retries=retries))
session.mount("http://", HTTPAdapter(max_retries=retries))


def test_expand_document_references_no_binary() -> None:
    dc_bundle = Bundle.parse_file("./tests/resources/DocumentReferencesNoBinary.json")

    output = expand_document_references_in_bundle(session=session, input_bundle=dc_bundle, base_url="https://hapi.fhir.org/baseR4/")

    assert isinstance(output, Bundle)
    assert output == dc_bundle
