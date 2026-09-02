from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from idp_pegawai.models.base import Base
from idp_pegawai.models.consumer import ConsumerChangeLog
from idp_pegawai.services.consumer import ConsumerService


def session():
    engine = create_engine("sqlite://")
    from idp_pegawai.models.consumer import ConsumerRegistration, ConsumerChangeLog
    ConsumerRegistration.__table__.create(engine)
    ConsumerChangeLog.__table__.create(engine)
    return Session(engine)


def test_registration_code_is_stable_and_not_reusable():
    with session() as db:
        service = ConsumerService(db)
        row = service.register("s1-internal", name="S1", owner_unit="unit", contact_email="s1@example.test", service_client_id="s1-feed", allowed_resource_families=["pegawai"], allowed_field_profile="pegawai-internal")
        assert service.register("s1-internal", name="updated", owner_unit="unit", contact_email="s1@example.test", service_client_id="s1-feed", allowed_resource_families=["pegawai"], allowed_field_profile="pegawai-internal") is row
        row.status = "revoked"
        db.flush()
        try:
            service.register("s1-internal", name="reuse", owner_unit="unit", contact_email="x", service_client_id="new", allowed_resource_families=["pegawai"], allowed_field_profile="p")
        except ValueError:
            pass
        else:
            raise AssertionError("revoked consumer_code must not be reusable")


def test_active_binding_is_unique():
    with session() as db:
        service = ConsumerService(db)
        service.register("one", name="One", owner_unit="u", contact_email="one@example.test", service_client_id="shared", allowed_resource_families=["pegawai"], allowed_field_profile="p")
        try:
            service.register("two", name="Two", owner_unit="u", contact_email="two@example.test", service_client_id="shared", allowed_resource_families=["pegawai"], allowed_field_profile="p")
        except ValueError:
            pass
        else:
            raise AssertionError("active service client binding must be unique")


def test_change_log_upsert_and_tombstone_are_action_specific_and_separate_from_outbox():
    with session() as db:
        service = ConsumerService(db)
        resource = uuid4()
        upsert = service.publish(resource, "pegawai", 4, {"pegawai_uuid": str(resource), "nama_lengkap": "A"}, "pegawai-internal", "pegawai-consumer.v1", "upsert")
        tombstone = service.publish(resource, "pegawai", 5, None, "pegawai-internal", "pegawai-consumer.v1", "tombstone")
        assert upsert.change_sequence == 1 and upsert.payload["nama_lengkap"] == "A"
        assert tombstone.change_sequence == 2 and tombstone.payload is None and tombstone.change_type == "tombstone"
        assert db.query(ConsumerChangeLog).count() == 2
        assert ConsumerChangeLog.__tablename__ != "outbox_events"


def test_change_sequence_is_monotonic_bigint():
    with session() as db:
        service = ConsumerService(db)
        a = service.publish(uuid4(), "pegawai", 1, {"x": 1}, "p", "v1")
        b = service.publish(uuid4(), "pegawai", 1, {"x": 2}, "p", "v1")
        assert b.change_sequence > a.change_sequence
        assert ConsumerChangeLog.__table__.c.change_sequence.type.__class__.__name__ == "BIGINT"
        assert ConsumerChangeLog.__table__.c.payload.nullable
        assert ConsumerChangeLog.__table__.c.payload_hash.nullable is False
