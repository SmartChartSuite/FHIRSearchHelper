'''File for custom models'''

from fhir.resources.R4B.capabilitystatement import CapabilityStatementRestResourceSearchParam
from pydantic import BaseModel


class SupportedSearchParams(BaseModel):

    resourceType: str
    searchParams: list[CapabilityStatementRestResourceSearchParam]


class QuerySearchParams(BaseModel):

    resourceType: str
    searchParams: dict[str, str]
