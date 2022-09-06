'''File for custom models'''

from pydantic import BaseModel

from fhir.resources.capabilitystatement import CapabilityStatementRestResourceSearchParam

class SupportedSearchParams(BaseModel):

    resourceType: str
    searchParams: CapabilityStatementRestResourceSearchParam

class QuerySearchParamsSearchParams(BaseModel):

    parameter: str
    value: str

class QuerySearchParams(BaseModel):

    resourceType: str
    searchParams: list[QuerySearchParamsSearchParams]