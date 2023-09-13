import pytest

from fhirsearchhelper.helpers.capabilitystatement import load_capability_statement, get_supported_search_params
from fhirsearchhelper.models.models import SupportedSearchParams
from fhir.resources.R4B.capabilitystatement import CapabilityStatement

def test_load_capability_statement_url() -> None:

    cs: CapabilityStatement = load_capability_statement(url='https://hapi.fhir.org/baseR4/metadata')

    assert cs.resource_type == 'CapabilityStatement'
    assert str(cs.implementation.url) == 'https://hapi.fhir.org/baseR4' #type: ignore


def test_load_capability_statement_file_path() -> None:

    cs: CapabilityStatement = load_capability_statement(file_path='epic_r4_metadata_edited.json')

    assert cs.resource_type == 'CapabilityStatement'
    assert str(cs.implementation.url) == 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4' #type: ignore


def test_load_capability_statement_no_args() -> None:

    with pytest.raises(ValueError):
        load_capability_statement()

def test_load_capability_statement_both_args() -> None:

    cs: CapabilityStatement = load_capability_statement(url='https://hapi.fhir.org/baseR4/metadata', file_path='epic_r4_metadata_edited.json')

    assert cs.resource_type == 'CapabilityStatement'
    assert str(cs.implementation.url) == 'https://hapi.fhir.org/baseR4' #type: ignore


def test_get_supported_search_params_capstate() -> None:

    cs: CapabilityStatement = load_capability_statement(file_path='epic_r4_metadata_edited.json')

    ssps: list[SupportedSearchParams] = get_supported_search_params(cs=cs)

    assert ssps
    assert isinstance(ssps, list)
    assert all([isinstance(sps, SupportedSearchParams) for sps in ssps])
    assert all([resource.type in [sps.resourceType for sps in ssps] for resource in cs.rest[0].resource if 'searchParam' in resource.dict(exclude_none=True)]) #type: ignore