"""Training editor Adapter: the ordinary validated/audited application command."""
from finance.expense_edit_audit import IExpenseEditCommand
from finance.expense_edit_repository import IExpenseRecordRepository
from finance.expense_record_serialization import records_as_json
from finance.expense_search import search_criteria_from_request
from .interfaces import EditIntentStorage, ExpenseCatalog
from .contracts import TrainingEditRequest
from pydantic import ValidationError


class TrainingExpenseEditor:
    def __init__(self, repository: IExpenseRecordRepository, catalog: ExpenseCatalog,
                 command: IExpenseEditCommand, store: EditIntentStorage):
        self.repository, self.catalog, self.command, self.store = repository, catalog, command, store

    def search(self, data: dict) -> dict:
        return {'ok': True, 'records': records_as_json(self.repository.search(search_criteria_from_request(data)))}

    def categories(self) -> dict:
        return {'ok': True, 'categories': self.catalog.options()}

    def edit(self, data: dict) -> dict:
        """A pending browser Command authorizes exactly one category-only edit.

        SQLite serializes duplicate deliveries. The repository also checks the
        stored row version under a MySQL row lock. A lost response is reconciled
        by reading the stored row, never by repeating an uncertain save.
        """
        try:
            data = TrainingEditRequest.model_validate(data).model_dump()
        except ValidationError as error:
            return {'ok': False, 'error': str(error)}
        operation_id = data['operation_id']
        with self.store.edit(operation_id) as transaction:
            intent = transaction.intent
            if intent is None:
                return {'ok': False, 'error': 'Start the requested edit through Toyota first.'}
            command = intent.command
            if command.action != 'category' or data.get('expense_id') != command.expense_id:
                return {'ok': False, 'error': 'The editor does not match the requested operation.'}
            expected = command.expected
            target = command.category_label
            required = {'merchant_name': expected['description'], 'transaction_date': expected['transaction_date'],
                        'total_amount': expected['total_amount'], 'distance_miles': expected['distance_miles'],
                        'map_link': expected['map_link'], 'category_name': target}
            if any(data.get(key) != value for key, value in required.items()):
                return {'ok': False, 'error': 'Only the explicitly requested category may change in this training operation.'}
            if intent.receipt:
                return intent.receipt
            if intent.status != 'claimed':
                return {'ok': False, 'error': 'This browser operation has not been claimed or was cancelled.'}
            current = records_as_json([self.repository.read(command.expense_id)])[0]
            unchanged = ('description', 'transaction_date', 'total_amount', 'distance_miles', 'map_link', 'notes')
            if current['category_id'] == command.category_id and all(current[k] == expected[k] for k in unchanged):
                result = {'ok': True, 'record': current, 'changed_fields': [], 'warnings': [], 'reconciled': True}
            elif current['version'] != expected['version']:
                return {'ok': False, 'error': 'This expense changed. Reload it and give a new instruction.'}
            else:
                request = {**data, 'expected_version': expected['version']}
                result = self.command.execute(request)
            transaction.complete(result)
            return result
