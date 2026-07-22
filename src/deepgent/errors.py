"""Exception hierarchy. User-facing handlers turn these into actionable messages."""


class DeepgentError(Exception):
    """Base class for all deepgent errors."""


class ConfigError(DeepgentError):
    """Configuration is missing, unreadable, or invalid."""


class TaskExecutionError(DeepgentError):
    """A task run failed before producing a result."""
