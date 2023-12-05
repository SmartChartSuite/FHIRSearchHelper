import pytest
from fhir.resources.R4B.capabilitystatement import CapabilityStatement
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from fhirsearchhelper.helpers.capabilitystatement import get_supported_search_params, load_capability_statement
from fhirsearchhelper.models.models import SupportedSearchParams

session: Session = Session()
retries: Retry = Retry(total=5, allowed_methods={"GET", "POST", "PUT", "DELETE"}, status_forcelist=[500])
session.mount("https://", HTTPAdapter(max_retries=retries))
session.mount("http://", HTTPAdapter(max_retries=retries))


def test_load_capability_statement_url() -> None:
    cs: CapabilityStatement = load_capability_statement(session=session, url="https://hapi.fhir.org/baseR4/metadata")

    assert cs.resource_type == "CapabilityStatement"
    assert str(cs.implementation.url) == "https://hapi.fhir.org/baseR4"  # type: ignore


def test_load_capability_statement_file_path() -> None:
    cs: CapabilityStatement = load_capability_statement(session=session, file_path="epic_r4_metadata_edited.json")

    assert cs.resource_type == "CapabilityStatement"
    assert str(cs.implementation.url) == "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"  # type: ignore


def test_load_capability_statement_no_args() -> None:
    with pytest.raises(ValueError):
        load_capability_statement(session=session)


def test_load_capability_statement_both_args() -> None:
    cs: CapabilityStatement = load_capability_statement(session=session, url="https://hapi.fhir.org/baseR4/metadata", file_path="epic_r4_metadata_edited.json")

    assert cs.resource_type == "CapabilityStatement"
    assert str(cs.implementation.url) == "https://hapi.fhir.org/baseR4"  # type: ignore


def test_get_supported_search_params_capstate() -> None:
    cs: CapabilityStatement = load_capability_statement(session=session, file_path="epic_r4_metadata_edited.json")

    ssps: list[SupportedSearchParams] = get_supported_search_params(cs=cs)

    assert ssps
    assert isinstance(ssps, list)
    assert all([isinstance(sps, SupportedSearchParams) for sps in ssps])
    assert all([resource.type in [sps.resourceType for sps in ssps] for resource in cs.rest[0].resource if "searchParam" in resource.dict(exclude_none=True)])  # type: ignore
