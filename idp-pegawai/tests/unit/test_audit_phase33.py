from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from idp_pegawai.audit.events import AuditEvent, make_event
from idp_pegawai.audit.redaction import redact_change_summary, validate_metadata
from idp_pegawai.audit.retention import RetentionPolicy, purge_candidates


def test_event_snapshots_actor_resource_scope_and_bounded_payload():
    event = make_event(
        event_type="pegawai.lifecycle_changed", outcome="success", severity="info",
        actor_type="pegawai", actor_subject="kc-subject", actor_pegawai_uuid=uuid4(),
        actor_scope_type="org_unit_subtree", actor_scope_org_unit_uuid=uuid4(),
        resource_type="pegawai", resource_uuid=uuid4(), scope_org_unit_uuid=uuid4(),
        scope_footprint=[uuid4(), uuid4()], changed_fields=["status_pegawai", "status_pegawai"],
        change_summary={"status_pegawai": {"before": "aktif", "after": "pensiun"}},
        metadata={"row_count": 1},
    )
    assert isinstance(event, AuditEvent)
    assert len(event.scope_footprint) == 2
    assert event.changed_fields == ("status_pegawai",)
    assert event.to_dict()["event_version"] == 1


def test_redaction_removes_secrets_raw_payload_and_pii():
    safe = redact_change_summary({"status_pegawai": {"before": "aktif", "after": "pensiun"},
                                  "email": "person@example.com", "password": "secret",
                                  "raw_payload": {"nip": "123456789"}, "nip": "123456789"})
    assert safe == {"status_pegawai": {"before": "aktif", "after": "pensiun"}}


def test_metadata_allowlist_is_small_and_rejects_sensitive_keys():
    assert validate_metadata("pegawai.lifecycle_changed", {"row_count": 2}) == {"row_count": 2}
    with pytest.raises(ValueError):
        validate_metadata("pegawai.lifecycle_changed", {"token": "abc"})


def test_retention_boundary_and_legal_hold():
    now = datetime.now(timezone.utc)
    policy = RetentionPolicy()
    old = {"occurred_at": now - timedelta(days=365 * 6), "retention_class": "security_access", "legal_hold": False}
    boundary = {"occurred_at": now - timedelta(days=365 * 5), "retention_class": "security_access", "legal_hold": False}
    held = {"occurred_at": now - timedelta(days=365 * 6), "retention_class": "security_access", "legal_hold": True}
    assert old in purge_candidates([old, boundary, held], now=now, policy=policy)
    assert boundary not in purge_candidates([old, boundary, held], now=now, policy=policy)
    assert held not in purge_candidates([old, boundary, held], now=now, policy=policy)


def test_event_rejects_unbounded_or_sensitive_payload():
    with pytest.raises(ValueError):
        make_event(event_type="x", outcome="success", severity="info", actor_type="system",
                   actor_subject="job", resource_type="pegawai", metadata={"password": "x"})
    with pytest.raises(ValueError):
        make_event(event_type="x", outcome="success", severity="info", actor_type="system",
                   actor_subject="job", resource_type="pegawai", changed_fields=[f"x{i}" for i in range(101)])
