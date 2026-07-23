"""Telemetry controller: task records and corpus candidates. Qt-free."""

from deepgent.telemetry import TaskRecord, TelemetryStore


class TelemetryController:
    def __init__(self, store: TelemetryStore | None = None) -> None:
        self._store = store

    def _get_store(self) -> TelemetryStore:
        if self._store is None:
            self._store = TelemetryStore()
        return self._store

    def records(self, limit: int = 100) -> list[TaskRecord]:
        return self._get_store().task_records(limit=limit)

    def get(self, task_id: str) -> TaskRecord | None:
        return self._get_store().get_task(task_id)
