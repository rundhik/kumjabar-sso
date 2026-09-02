from datetime import datetime, timedelta, timezone
import pytest

from idp_pegawai.consumer.freshness import (
    ConsumerState, ConflictError, OutOfOrderError, apply_page,
    classify_freshness,
)


def item(version, digest, *, resource="r1", change_type="upsert", occurred_at=None):
    return {"resource_uuid": resource, "source_version": version,
            "payload_hash": digest, "payload": None if change_type == "tombstone" else {"v": version},
            "change_type": change_type, "occurred_at": occurred_at}


def test_duplicate_is_noop_and_lower_version_is_rejected_or_handled():
    state = ConsumerState()
    assert state.apply(item(2, "a")) == "applied"
    assert state.apply(item(2, "a")) == "duplicate"
    assert state.apply(item(1, "old")) == "stale"


def test_same_version_different_hash_is_conflict():
    state = ConsumerState(); state.apply(item(2, "a"))
    with pytest.raises(ConflictError): state.apply(item(2, "b"))


def test_tombstone_requires_newer_version_and_is_retained():
    state = ConsumerState(); state.apply(item(2, "a"))
    assert state.apply(item(3, "dead", change_type="tombstone")) == "applied"
    assert state.get("r1").tombstone is True
    assert state.apply(item(2, "old", change_type="tombstone")) == "stale"


def test_page_rolls_back_when_one_item_conflicts():
    state = ConsumerState(); state.apply(item(1, "a"))
    with pytest.raises(ConflictError): apply_page(state, [item(2, "b"), item(2, "different")])
    assert state.get("r1").source_version == 1


def test_freshness_and_lag_classification():
    now = datetime.now(timezone.utc)
    assert classify_freshness(2, "a", 2, "a", now=now, observed_at=now) == "fresh"
    assert classify_freshness(1, "a", 2, "b", now=now, observed_at=now) == "stale"
    assert classify_freshness(2, "a", 2, "a", now=now, observed_at=now-timedelta(minutes=5), max_lag=60) == "lagging"
    assert classify_freshness(None, None, 2, "a") == "unknown"

    