from fhirsearchhelper.helpers.documenthelper import expand_document_references_in_bundle
from fhir.resources.R4B.bundle import Bundle


def test_expand_document_references_no_binary() -> None:

    dc_bundle = Bundle.parse_file('./tests/resources/DocumentReferencesNoBinary.json')

    output = expand_document_references_in_bundle(dc_bundle, 'https://hapi.fhir.org/baseR4/')

    assert isinstance(output, Bundle)
    assert output == dc_bundle