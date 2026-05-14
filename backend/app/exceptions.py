"""Domain exceptions mapped to HTTP responses in ``error_handlers`` (T013)."""


class NotFoundError(Exception):
    """Missing entity (→ 404)."""


class WIPLimitError(Exception):
    """Kanban WIP rule violated (→ 409)."""


class DuplicateNameError(Exception):
    """Unique name constraint violated (→ 409)."""


class InvalidTransitionError(Exception):
    """Illegal state transition or disallowed follow-up action (→ 400)."""


class SandboxEscapeError(Exception):
    """Path or command outside sandbox root (→ 400)."""


class PauseSignal(Exception):
    """Coder detected a task-level pause (Redis); run stops after status/event persist (US11 / T086)."""
