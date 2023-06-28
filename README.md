# FHIR Search Helper

<a href="https://pypi.python.org/pypi/fhirsearchhelper" rel="PyPi Package Link">![PyPi Package Link](https://img.shields.io/pypi/v/fhirsearchhelper.svg)</a>
<a href="https://pypi.python.org/pypi/fhirsearchhelper" rel="Supported Python versions">![Supported Python versions](https://img.shields.io/pypi/pyversions/fhirsearchhelper.svg)</a>
[![Downloads](https://pepy.tech/badge/fhirsearchhelper)](https://pepy.tech/project/fhirsearchhelper)

A Python package to support FHIR Searching in contexts where needed search parameters are not supported

## Quick Start

*NOTE*: Currently, the only option for capability_statement_file is 'epic_r4_metadata_edited.json'

``` python
from fhirsearchhelper import run_fhir_query

# This is using objects to store search params
output: Bundle | None = run_fhir_query(base_url='https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/', query_headers={'Authorization': 'Bearer 1234567'}, resource_type='Patient', search_params={'resourceType': 'Patient', 'search_params': {'name': 'Smith', 'deceased': 'true'}}, capability_statement_file='epic_r4_metadata_edited.json')

# This is using a raw query
output: Bundle | None = run_fhir_query(query_headers={'Authorization': 'Bearer 1234567'}, query='https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/Patient?name=Smith&deceased=true', capability_statement_file='epic_r4_metadata_edited.json')
```

## A Note on CapabilityStatements

In their current form, `CapabilityStatement`s do not have a way to express when a search parameter for a resource is conditionally accepted. For example, in the Epic R4 `CapabilityStatement`, for the `Condition` resource, there exists a listed search parameter of `code`. In the description, there is a note that this search parameter is only accepted when the `category` is equal to `infection`. The only way that this conditional information would be known is by manual reading of the description. To alleviate this issue, and to avoid extreme custom handling in this package, currently you must edit the `CapabilityStatement` of any server with which you would like to use this package and add custom extensions to the search parameter. Keeping with the above example of the search parameter `code` for the `Condition` resource, here is what the `CapabilityStatement.rest[0].resource.where(type = 'Condition').searchParam.where(name = 'code')` element looks like:

``` json
{
    "name": "code",
    "type": "token",
    "documentation": "Search for Conditions with a specified code. This is only used when searching for infections.",
    "extension": [
        {
            "url": "true-when",
            "valueString": "category==infection"
        }
    ]
}
```

Here we have added an extension with a url of `true-when` that is a machine readable statement denoting when a search parameter is accepted by the server. It currently only supports == to show equality and in to show membership of a list (e.g. "category in [infection, health-problem]"). This also works for when a search parameter is limited in the values it will successfully search for. For example, here is what the `CapabilityStatement.rest[0].resource.where(type = 'Condition').searchParam.where(name = 'category')` element looks like:

``` json
{
    "name": "category",
    "type": "token",
    "documentation": "Search for Condition resources by category.",
    "extension": [
        {
            "url": "true-when",
            "valueString": "category in [dental-finding, encounter-diagnosis, genomics, health-concern, infection, medical-history, problem-list-item, reason-for-visit]"
        }
    ]
}
```