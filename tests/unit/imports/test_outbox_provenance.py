import pytest
from uuid import uuid4

from idp_pegawai.imports.apply import apply_with_outbox
from idp_pegawai.models.outbox_event import OutboxEvent


def test_apply_writes_bounded_provenance_event_in_same_session_transaction():
    state = {"status": "ready_to_apply", "rows": []}
    session = _Session()

    apply_with_outbox(
        state,
        lambda: state["rows"].append("created"),
        session=session,
        batch_uuid=uuid4(),
        result_summary={"created": 1, "updated": 0, "noop": 0},
    )

    assert state["status"] == "applied"
    assert len(session.added) == 1
    event = session.added[0]
    assert isinstance(event, OutboxEvent)
    assert event.event_type == "pegawai.import.applied"
    assert event.provenance["batch_uuid"]
    assert event.payload == {"created": 1, "updated": 0, "noop": 0}
    assert "nama" not in str(event.payload).lower()
    assert "email" not in str(event.payload).lower()
    assert "nip" not in str(event.payload).lower()
    assert session.commits == 1


def test_apply_rolls_back_domain_and_does_not_enqueue_on_failure():
    state = {"status": "ready_to_apply", "rows": []}
    session = _Session()

    with pytest.raises(RuntimeError):
        apply_with_outbox(state, _failing_mutation(state), session=session, batch_uuid=uuid4(), result_summary={"created": 1})

    assert state == {"status": "ready_to_apply", "rows": []}
    assert session.added == []
    assert session.rollbacks == 1


class _Transaction:
    def __init__(self, session): self.session = session
    def __enter__(self): return self
    def __exit__(self, typ, value, tb):
        if typ is None: self.session.commits += 1


class _Session:
    def __init__(self): self.added, self.commits, self.rollbacks = [], 0, 0
    def begin(self): return _Transaction(self)
    def add(self, obj): self.added.append(obj)
    def rollback(self): self.rollbacks += 1


def _failing_mutation(state):
    def mutate():
        state["status"] = "applying"
        state["rows"].append("partial")
        raise RuntimeError("constraint")
    return mutate
