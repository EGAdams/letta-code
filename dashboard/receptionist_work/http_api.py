"""Thin HTTP adapter; application policy stays behind its injected ports."""
from . import composition


def state():
    return composition.work_application().state()


def execute(data):
    return composition.work_application().execute(data)


def claim(data):
    return composition.work_application().claim(data)


def training_search(data):
    return composition.training_editor().search(data)


def training_categories():
    return composition.training_editor().categories()


def training_edit(data):
    return composition.save_command().execute(data)


def document_path(path):
    return composition.document_path(path)


def trace(run_id):
    from . import trace_reader
    from .contracts import WorkState
    state = WorkState.model_validate(composition.work_application().state()['state'])
    return trace_reader.trace(run_id, state)
