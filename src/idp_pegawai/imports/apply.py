"""Atomic application of an already validated import plan.

This module deliberately owns no I/O and makes no remote calls.  Callers inject
any persistence work as ``apply_callback`` and, when applicable, a database
session whose transaction surrounds that work.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable
from idp_pegawai.models.outbox_event import OutboxEvent


def _set_status(state: Any, status: str) -> None:
    if isinstance(state, dict):
        state["status"] = status
    else:
        setattr(state, "status", status)


def atomic_apply(
    state: Any,
    apply_callback: Callable[[], Any],
    *,
    success_status: str = "applied",
    session: Any | None = None,
) -> Any:
    """Run an apply callback atomically and leave ``state`` in a terminal state.

    The callback is the only application operation; this function performs no
    remote work.  A snapshot is restored on any failure so an in-memory state
    cannot remain ``applying`` or retain partial rows.  If a session is
    supplied, its transaction context encloses the callback and rolls back on
    failure (SQLAlchemy sessions and compatible test doubles are supported).
    """
    snapshot = deepcopy(state)

    def run() -> Any:
        result = apply_callback()
        _set_status(state, success_status)
        return result

    try:
        if session is None:
            return run()
        # begin() is preferred: its context manager commits only after the
        # callback and terminal state have succeeded, and rolls back otherwise.
        begin = getattr(session, "begin", None)
        if begin is not None:
            with begin():
                return run()
        return run()
    except BaseException:
        if session is not None:
            rollback = getattr(session, "rollback", None)
            if rollback is not None:
                rollback()
        # Restore the caller-owned object in place, preserving its identity.
        if isinstance(state, dict) and isinstance(snapshot, dict):
            state.clear()
            state.update(snapshot)
        elif hasattr(state, "__dict__") and hasattr(snapshot, "__dict__"):
            state.__dict__.clear()
            state.__dict__.update(snapshot.__dict__)
        raise


def apply_with_outbox(state: Any, apply_callback: Callable[[], Any], *, session: Any, batch_uuid: Any, result_summary: dict[str, int]) -> Any:
    snapshot = deepcopy(state)
    try:
        with session.begin():
            result = apply_callback()
            _set_status(state, "applied")
            session.add(OutboxEvent(event_type="pegawai.import.applied", aggregate_uuid=batch_uuid,
                provenance={"batch_uuid": str(batch_uuid), "contract_version": "import.apply.v1"},
                payload={k: int(result_summary.get(k, 0)) for k in ("created", "updated", "noop")}))
            return result
    except BaseException:
        session.rollback()
        if isinstance(state, dict): state.clear(); state.update(snapshot)
        raise


__all__ = ["atomic_apply", "apply_with_outbox"]
