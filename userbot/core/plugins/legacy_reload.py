"""Rollback of legacy registration state during synchronous trusted-plugin imports.

This is not a sandbox: file writes, network effects and arbitrary import-created
tasks cannot be rolled back. Call only on the client's event-loop thread, without
yielding between entering this transaction and completing the import.
"""


def _containers(value):
    if isinstance(value, dict):
        return {k: _containers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_containers(v) for v in value]
    if isinstance(value, set):
        return value.copy()
    return value


class RegistrationTransaction:
    def __init__(self, clients, mappings, sequences=()):
        self.clients = [c for c in clients if c is not None]
        self.mappings = mappings
        self.sequences = sequences

    def __enter__(self):
        self.handlers = [list(c._event_builders) for c in self.clients]
        self.maps = [_containers(m) for m in self.mappings]
        self.lists = [_containers(s) for s in self.sequences]
        return self

    def __exit__(self, kind, error, traceback):
        if kind is not None:
            for client, handlers in zip(self.clients, self.handlers):
                client._event_builders[:] = handlers
            for target, original in zip(self.mappings, self.maps):
                target.clear()
                target.update(original)
            for target, original in zip(self.sequences, self.lists):
                target[:] = original
        return False
