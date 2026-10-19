"""Facade over workflow Commands and retained assignment state."""
from .contracts import ClaimRequest, WorkRequest
from .interfaces import WorkStorage, WorkflowRunner


class ReceptionistWorkApplication:
    def __init__(self, runner: WorkflowRunner, storage: WorkStorage):
        self.runner, self.storage = runner, storage

    def state(self) -> dict:
        return {'ok': True, 'state': self.storage.read('toyota').model_dump(mode='json')}

    def execute(self, data: dict) -> dict:
        request = WorkRequest.model_validate(data)
        return self.runner.run(request).model_dump(mode='json')

    def claim(self, data: dict) -> dict:
        request = ClaimRequest.model_validate(data)
        command = self.storage.claim(request.command_id, request.client_id)
        return {'ok': command is not None,
                'command': command.model_dump(mode='json') if command else None}
