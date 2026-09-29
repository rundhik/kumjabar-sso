from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from idp_pegawai.consumer.cursor import CursorSigner, CursorError
from idp_pegawai.consumer.feed import DeltaFeedService, FeedError, PageLimitError, ReplayExpiredError


def setup_feed():
    registration = type("Registration", (), {"consumer_code": "s1", "uuid": uuid4(), "allowed_field_profile": "pegawai.v1", "max_page_size": 100, "replay_window_days": 30})()
    signer = CursorSigner(active_key_id="k1", keys={"k1": b"secret"})
    records = [type("Row", (), {"change_sequence": i, "resource_type": "pegawai", "resource_uuid": uuid4(), "change_type": "upsert", "source_version": i, "contract_version": "consumer-change.v1", "field_profile": "pegawai.v1", "payload_hash": "a" * 64, "payload": {"status": "active", "org_unit_code": "A"}})() for i in range(1, 4)]
    return DeltaFeedService(signer=signer, records=records), registration


def test_feed_pages_and_emits_bound_next_cursor_without_pii():
    feed, reg = setup_feed()
    result = feed.read(registration=reg, resource_family="pegawai", limit=2)
    assert [x["change_sequence"] for x in result.items] == [1, 2]
    assert result.next_cursor
    assert "nip" not in str(result.items)
    result2 = feed.read(registration=reg, resource_family="pegawai", limit=2, cursor=result.next_cursor)
    assert [x["change_sequence"] for x in result2.items] == [3]

@pytest.mark.parametrize("limit", [0, 501, "2"])
def test_page_limit_is_rejected(limit):
    feed, reg = setup_feed()
    with pytest.raises(PageLimitError):
        feed.read(registration=reg, resource_family="pegawai", limit=limit)

def test_tampered_and_binding_cursor_are_rejected():
    feed, reg = setup_feed()
    cursor = feed.read(registration=reg, resource_family="pegawai", limit=1).next_cursor
    with pytest.raises(CursorError):
        feed.read(registration=reg, resource_family="org-unit", limit=1, cursor=cursor)
    with pytest.raises(CursorError):
        feed.read(registration=reg, resource_family="pegawai", limit=1, cursor=cursor[:-1] + "x")

def test_expired_cursor_is_rejected_as_replay_expired():
    feed, reg = setup_feed()
    old = feed.signer.encode(consumer_code="s1", registration_uuid=str(reg.uuid), resource_family="pegawai", field_profile="pegawai.v1", contract_version="consumer-change.v1", position=0, issued_at=datetime.now(timezone.utc)-timedelta(days=31), expires_at=datetime.now(timezone.utc)-timedelta(days=1))
    with pytest.raises(ReplayExpiredError):
        feed.read(registration=reg, resource_family="pegawai", limit=1, cursor=old)

def test_pii_in_record_is_not_returned():
    feed, reg = setup_feed()
    feed.records[0].payload = {"status": "active", "nip": "secret", "nested": {"email": "x"}}
    with pytest.raises(FeedError):
        feed.read(registration=reg, resource_family="pegawai", limit=1)


def test_invalid_cursor_is_feed_error():
    feed, reg = setup_feed()
    with pytest.raises(CursorError):
        feed.read(registration=reg, resource_family="pegawai", limit=1, cursor="bad")


def test_tombstone_has_no_payload():
    feed, reg = setup_feed()
    feed.records[0].change_type = "tombstone"
    feed.records[0].payload = None
    assert feed.read(registration=reg, resource_family="pegawai", limit=1).items[0]["payload"] is None
    

def test_no_pii_names_in_output_schema():
    feed, reg = setup_feed()
    item = feed.read(registration=reg, resource_family="pegawai", limit=1).items[0]
    assert set(item) == {"change_sequence", "resource_type", "resource_uuid", "change_type", "source_version", "contract_version", "field_profile", "payload_hash", "payload"}
    assert not any(k in item for k in ("source_outbox_event_id", "occurred_at"))