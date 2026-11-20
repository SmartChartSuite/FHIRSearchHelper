import httpx
import pytest
from fhir.resources.R4B.capabilitystatement import CapabilityStatement

from fhirsearchhelper.helpers.capabilitystatement import get_supported_search_params, load_capability_statement
from fhirsearchhelper.helpers.gapanalysis import run_gap_analysis
from fhirsearchhelper.main import _build_query_string
from fhirsearchhelper.models.models import QuerySearchParams, SupportedSearchParams

transport: httpx.HTTPTransport = httpx.HTTPTransport(retries=5)
client: httpx.Client = httpx.Client(transport=transport)


def test_load_capability_statement_url() -> None:
    cs: CapabilityStatement = load_capability_statement(client=client, url="https://hapi.fhir.org/baseR4/metadata")

    assert cs.__resource_type__ == "CapabilityStatement"
    assert str(cs.implementation.url) == "https://hapi.fhir.org/baseR4"  # type: ignore


def test_load_capability_statement_file_path() -> None:
    cs: CapabilityStatement = load_capability_statement(client=client, file_path="epic_r4_metadata_edited.json")

    assert cs.__resource_type__ == "CapabilityStatement"
    assert str(cs.implementation.url) == "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"  # type: ignore


def test_load_capability_statement_no_args() -> None:
    with pytest.raises(ValueError):
        load_capability_statement(client=client)


def test_load_capability_statement_both_args() -> None:
    cs: CapabilityStatement = load_capability_statement(client=client, url="https://hapi.fhir.org/baseR4/metadata", file_path="epic_r4_metadata_edited.json")

    assert cs.__resource_type__ == "CapabilityStatement"
    assert str(cs.implementation.url) == "https://hapi.fhir.org/baseR4" if cs.implementation else True


def test_get_supported_search_params_capstate() -> None:
    cs: CapabilityStatement = load_capability_statement(client=client, file_path="epic_r4_metadata_edited.json")

    ssps: list[SupportedSearchParams] = get_supported_search_params(cs=cs)

    assert ssps
    assert isinstance(ssps, list)
    assert all(isinstance(sps, SupportedSearchParams) for sps in ssps)
    assert all(resource.type in [sps.resourceType for sps in ssps] for resource in cs.rest[0].resource if "searchParam" in resource.model_dump(exclude_none=True))  # type: ignore


def test_epic_condition_code_is_forwarded_to_upstream() -> None:
    capability_statement = load_capability_statement(client=client, file_path="epic_r4_metadata_edited.json")
    supported_search_params = get_supported_search_params(cs=capability_statement)
    query = QuerySearchParams(
        resourceType="Condition",
        searchParams={"patient": "patient-1", "code": "http://hl7.org/fhir/sid/icd-10-cm|O14.10"},
        searchParamsList=[("patient", "patient-1"), ("code", "http%3A%2F%2Fhl7.org%2Ffhir%2Fsid%2Ficd-10-cm%7CO14.10")],
    )

    gap_output = run_gap_analysis(supported_search_params=supported_search_params, query_search_params=query)

    assert gap_output == []
    assert _build_query_string(search_params=query, gap_output=gap_output) == (
        "Condition?patient=patient-1&code=http%3A%2F%2Fhl7.org%2Ffhir%2Fsid%2Ficd-10-cm%7CO14.10"
    )
