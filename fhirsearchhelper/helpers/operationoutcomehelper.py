'''File to handle all operations around OperationOutcomes'''

import logging

logger: logging.Logger = logging.getLogger('fhirsearchhelper.operationoutcomehelper')

def handle_operation_outcomes(resource: dict) -> None:
    issue_codes = [issue['code'] for issue in resource['issue'] if 'code' in issue]
    issue_details = [issue['details']['text'] for issue in resource['issue'] if 'details' in issue and 'text' in issue['details']]
    issue_diagnostics = [issue['diagnostics'] for issue in resource['issue'] if 'diagnostics' in issue]
    logger.warning(f'There was an OperationOutcome in the return bundle with codes {issue_codes}')
    logger.warning(f'There was an OperationOutcome in the return bundle with issue details of {issue_details}')
    logger.warning(f'There was an OperationOutcome in the return bundle with issue diagnostics of {issue_diagnostics}')