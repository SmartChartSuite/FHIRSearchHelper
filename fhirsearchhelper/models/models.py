'''File for custom models'''

from pydantic import BaseModel

from fhir.resources.R4B.capabilitystatement import CapabilityStatementRestResourceSearchParam


class SupportedSearchParams(BaseModel):

    resourceType: str
    searchParams: list[CapabilityStatementRestResourceSearchParam]


class QuerySearchParams(BaseModel):

    resourceType: str
    searchParams: dict[str, str]
