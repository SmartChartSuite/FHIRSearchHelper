from fhirsearchhelper.helpers.fhirfilter import filter_bundle
from fhirsearchhelper.models.models import QuerySearchParams

from fhir.resources.R4B.bundle import Bundle


def test_filter_bundle_new() -> None:
    input_bundle: Bundle = Bundle.parse_file(
        "./tests/resources/FHIRFilterInputBundle.json"
    )
    search_params: QuerySearchParams = QuerySearchParams(
        resourceType="Condition",
        searchParams={
            "patient": "eZ5-7rYdWqgv3jSgIvx.SPw3",
            "category": "encounter-diagnosis",
            "code": "http://snomed.info/sct|110483000",
        },
    )
    gap_analysis_output: list[str] = ["code"]

    filtered_bundle: Bundle = filter_bundle(
        input_bundle=input_bundle,
        search_params=search_params,
        gap_analysis_output=gap_analysis_output,
    )

    assert filtered_bundle.total < input_bundle.total
    assert filtered_bundle.total == len(filtered_bundle.entry)

    for entry in filtered_bundle.entry:
        assert "eZ5-7rYdWqgv3jSgIvx.SPw3" == entry["resource"]["subject"]["reference"].split("/")[1]
        assert "encounter-diagnosis" in [cat["coding"][0]["code"] for cat in entry["resource"]["category"]]
        assert any(["http://snomed.info/sct|110483000".split("|")[1] == coding["code"] for coding in entry["resource"]["code"]["coding"]])
