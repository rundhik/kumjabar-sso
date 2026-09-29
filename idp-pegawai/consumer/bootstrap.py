"""Transport-neutral consumer bootstrap cutoff and checkpoint handoff core."""
from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from typing import Callable, Iterable


class BootstrapError(ValueError):
    """Bootstrap state, cursor, or apply contract is invalid."""


@dataclass(frozen=True)
class BootstrapPage:
    items: list[object]
    next_page_cursor: str | None
    has_more: bool


class BootstrapSession:
    def __init__(self, coordinator: "BootstrapCoordinator", cutoff_sequence: int, page_size: int):
        self._coordinator = coordinator
        self.cutoff_sequence = cutoff_sequence
        self._page_size = page_size
        self._position = 0
        self._applied = False
        self._complete = False
        self._cursor = self._new_cursor(0)

    def _new_cursor(self, position: int) -> str:
        cursor = token_urlsafe(24)
        self._coordinator._cursors[cursor] = (self, position)
        return cursor

    def page(self) -> BootstrapPage:
        rows = self._coordinator._rows
        selected = rows[self._position : self._position + self._page_size]
        next_position = self._position + len(selected)
        more = next_position < len(rows)
        cursor = self._new_cursor(next_position) if more else None
        return BootstrapPage(selected, cursor, more)

    def advance(self, cursor: str) -> "BootstrapSession":
        value = self._coordinator._cursors.get(cursor)
        if value is None or value[0] is not self:
            raise BootstrapError("invalid bootstrap page cursor")
        self._position = value[1]
        self._applied = False
        return self

    def apply_page(self, *, status_code: int, applied: bool) -> bool:
        # Delivery success is deliberately not local transaction success.
        self._applied = bool(applied)
        return self._applied

    def complete(self, checkpoint: str) -> str:
        if not isinstance(checkpoint, str) or not checkpoint:
            raise BootstrapError("checkpoint must be opaque and non-empty")
        if self.page().has_more or not self._applied:
            raise BootstrapError("bootstrap pages and checkpoint apply must commit first")
        self._complete = True
        return checkpoint

    def continue_changes(self, checkpoint: str) -> str:
        if not self._complete or not isinstance(checkpoint, str) or not checkpoint:
            raise BootstrapError("bootstrap is not complete")
        return checkpoint


class BootstrapCoordinator:
    def __init__(self, *, rows: Iterable[object], capture_cutoff: Callable[[], int] | None = None):
        self._rows = sorted(list(rows), key=lambda row: row.change_sequence)
        self._capture_cutoff = capture_cutoff or self._default_cutoff
        self._cursors: dict[str, tuple[BootstrapSession, int]] = {}

    def _default_cutoff(self) -> int:
        return max((row.change_sequence for row in self._rows), default=0)

    def start(self, *, page_size: int = 100) -> BootstrapSession:
        if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size < 1:
            raise BootstrapError("page size must be positive")
        cutoff = self._capture_cutoff()
        if isinstance(cutoff, bool) or not isinstance(cutoff, int) or cutoff < 0:
            raise BootstrapError("cutoff must be a non-negative sequence")
        # Filter after one cutoff capture: later rows cannot enter this run.
        self._rows = [row for row in self._rows if row.change_sequence <= cutoff]
        return BootstrapSession(self, cutoff, page_size)


__all__ = ["BootstrapCoordinator", "BootstrapError", "BootstrapPage", "BootstrapSession"]
