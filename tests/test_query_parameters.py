from fhir.resources.R4B.capabilitystatement import CapabilityStatementRestResourceSearchParam

from fhirsearchhelper.helpers.gapanalysis import run_gap_analysis
from fhirsearchhelper.main import _build_query_string, _parse_query_parameters
from fhirsearchhelper.models.models import QuerySearchParams, SupportedSearchParams


def test_parse_query_parameters_preserves_repeated_names() -> None:
    values, pairs = _parse_query_parameters("patient=123&date=ge%3C2024-01-01&date=le%3C2024-12-31")

    assert values == {"patient": "123", "date": "le%3C2024-12-31"}
    assert pairs == [
        ("patient", "123"),
        ("date", "ge%3C2024-01-01"),
        ("date", "le%3C2024-12-31"),
    ]


def test_build_query_string_preserves_repeated_date_bounds() -> None:
    search_params = QuerySearchParams(
        resourceType="DocumentReference",
        searchParams={"patient": "123", "date": "le%3C2024-12-31"},
        searchParamsList=[
            ("patient", "123"),
            ("date", "ge%3C2024-01-01"),
            ("date", "le%3C2024-12-31"),
        ],
    )

    assert _build_query_string(search_params, gap_output=[]) == (
        "DocumentReference?patient=123&date=ge%3C2024-01-01&date=le%3C2024-12-31"
    )


def test_build_query_string_falls_back_to_dict_for_programmatic_queries() -> None:
    search_params = QuerySearchParams(resourceType="Patient", searchParams={"patient": "123"})

    assert _build_query_string(search_params, gap_output=[]) == "Patient?patient=123"


def test_not_modifier_matches_supported_base_parameter() -> None:
    supported = [
        SupportedSearchParams(
            resourceType="Observation",
            searchParams=[CapabilityStatementRestResourceSearchParam(name="code", type="token")],
        )
    ]
    query = QuerySearchParams(
        resourceType="Observation",
        searchParams={"code:not": "http://loinc.org|1234-5"},
        searchParamsList=[("code:not", "http://loinc.org|1234-5")],
    )

    assert run_gap_analysis(supported_search_params=supported, query_search_params=query) == ["code:not"]
