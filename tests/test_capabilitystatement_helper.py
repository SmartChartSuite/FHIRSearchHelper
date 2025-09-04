import httpx
import pytest
from fhir.resources.R4B.capabilitystatement import CapabilityStatement

from fhirsearchhelper.helpers.capabilitystatement import get_supported_search_params, load_capability_statement
from fhirsearchhelper.models.models import SupportedSearchParams

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
    assert all([isinstance(sps, SupportedSearchParams) for sps in ssps])
    assert all([resource.type in [sps.resourceType for sps in ssps] for resource in cs.rest[0].resource if "searchParam" in resource.dict(exclude_none=True)])  # type: ignore
