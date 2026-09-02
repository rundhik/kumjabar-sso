from datetime import datetime, timedelta, timezone
from uuid import uuid4

from idp_pegawai import create_app
from idp_pegawai.consumer.cursor import CursorSigner
from idp_pegawai.consumer.feed import DeltaFeedService


def setup_api():
    registration = type("Registration", (), {"consumer_code": "s1", "uuid": uuid4(),
        "allowed_field_profile": "pegawai.v1", "max_page_size": 100})()
    signer = CursorSigner(active_key_id="k1", keys={"k1": b"secret"})
    rows = [type("Row", (), {"change_sequence": i, "resource_type": "pegawai",
        "resource_uuid": uuid4(), "change_type": "upsert", "source_version": i,
        "contract_version": "consumer-change.v1", "field_profile": "pegawai.v1",
        "payload_hash": "a" * 64, "payload": {"status": "active"}})() for i in range(1, 3)]
    feed = DeltaFeedService(signer=signer, records=rows)
    app = create_app({"TESTING": True, "INTERNAL_FEED_SERVICE": feed,
        "INTERNAL_FEED_REGISTRATIONS": {"s1": registration}})
    return app, registration, feed


def test_delta_feed_contract_and_cursor_binding():
    app, _, _ = setup_api()
    client = app.test_client()
    response = client.get("/internal/feed/pegawai?limit=1", headers={"X-Consumer-Code": "s1"})
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["items"]) == 1 and body["next_cursor"]
    assert set(body["items"][0]) == {"change_sequence", "resource_type", "resource_uuid", "change_type", "source_version", "contract_version", "field_profile", "payload_hash", "payload"}
    assert "nip" not in str(body)
    assert client.get("/internal/feed/pegawai?limit=501", headers={"X-Consumer-Code": "s1"}).status_code == 400
    assert client.get("/internal/feed/pegawai?cursor=bad", headers={"X-Consumer-Code": "s1"}).status_code == 400
    assert client.get("/internal/feed/pegawai", headers={"X-Consumer-Code": "other"}).status_code == 401


def test_expired_cursor_is_gone():
    app, registration, feed = setup_api()
    token = feed.signer.encode(consumer_code="s1", registration_uuid=str(registration.uuid), resource_family="pegawai", field_profile="pegawai.v1", contract_version="consumer-change.v1", position=0, issued_at=datetime.now(timezone.utc) - timedelta(days=2), expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert app.test_client().get("/internal/feed/pegawai?cursor=" + token, headers={"X-Consumer-Code": "s1"}).status_code == 410