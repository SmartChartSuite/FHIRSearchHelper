'''File to perform the search parameter gap analysis'''

import logging

from fhir.resources.R4B.capabilitystatement import CapabilityStatementRestResourceSearchParam

from ..models.models import QuerySearchParams, SupportedSearchParams

logger: logging.Logger = logging.getLogger('fhirsearchhelper.gapanalysis')


def run_gap_analysis(supported_search_params: list[SupportedSearchParams], query_search_params: QuerySearchParams) -> list[str]:
    resource_type = query_search_params.resourceType

    resouce_supported_search_params: SupportedSearchParams = list(filter(lambda x: x.resourceType == resource_type, supported_search_params))[0]

    query_params_names = list(query_search_params.searchParams.keys())
    temp_supported_params_names: list[str] = [rsc.name for rsc in resouce_supported_search_params.searchParams]

    supported_params_names = []
    for name in temp_supported_params_names:
        search_param_obj: CapabilityStatementRestResourceSearchParam = list(filter(lambda x: x.name == name, resouce_supported_search_params.searchParams))[0]
        if search_param_obj.extension:
            filtered_ext_list = list(filter(lambda x: x.url == 'true-when', search_param_obj.extension)) # type: ignore
            if filtered_ext_list:
                if '==' in filtered_ext_list[0].valueString:
                    field, value = filtered_ext_list[0].valueString.split('==')
                    if field in query_params_names and query_search_params.searchParams[field] == value:
                        supported_params_names.append(name)
                elif ' in ' in filtered_ext_list[0].valueString:
                    field, values = filtered_ext_list[0].valueString.split(' in ')
                    values = [value.strip() for value in  values.strip('[').strip(']').split(',')]
                    if (field in query_params_names
                        and len(query_search_params.searchParams[field].split(',')) > 1
                        and all([sp_value in values for sp_value in query_search_params.searchParams[field].split(',')])):
                        supported_params_names.append(name)
                        continue
                    if field in query_params_names and query_search_params.searchParams[field] in values:
                        supported_params_names.append(name)
        else:
            supported_params_names.append(name)

    params_not_supported = [name for name in query_params_names if name not in supported_params_names]

    return params_not_supported