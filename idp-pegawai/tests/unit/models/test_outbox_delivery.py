from datetime import datetime, timezone
from uuid import uuid4

from idp_pegawai.models.outbox_delivery import DeliveryStatus, OutboxConsumerDelivery


def test_delivery_model_matches_in_memory_state_machine_contract():
    delivery = OutboxConsumerDelivery(
        outbox_event_id=42,
        consumer_code="keycloak_projection_v1",
    )

    assert delivery.status == DeliveryStatus.PENDING.value
    assert delivery.dispatch_attempt_count == 0
    assert delivery.lease_generation == 0
    assert delivery.lease_owner is None
    assert delivery.dispatched_job_id is None
    assert delivery.uuid
    assert delivery.consumer_code == "keycloak_projection_v1"


def test_delivery_model_has_durable_state_and_error_fields():
    expected = {
        "outbox_event_id", "consumer_code", "status",
        "dispatch_attempt_count", "next_dispatch_at", "lease_owner",
        "lease_until", "lease_generation", "last_error_code", "last_error_at",
        "dispatched_job_id", "dispatched_at", "created_at", "updated_at",
    }
    assert expected <= set(OutboxConsumerDelivery.__table__.columns.keys())
    assert {"outbox_event_id", "consumer_code"} <= {
        column.name for constraint in OutboxConsumerDelivery.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
        for column in constraint.columns
    }


def test_delivery_status_values_are_shared_with_contract():
    assert {status.value for status in DeliveryStatus} == {
        "pending", "claiming", "dispatched", "retry_wait", "blocked", "dead_letter"
    }
    assert OutboxConsumerDelivery.__table__.c.status.default.arg == "pending"


def test_dispatched_job_is_unique_when_present():
    assert any(
        index.name == "uq_outbox_consumer_deliveries_dispatched_job_id"
        for index in OutboxConsumerDelivery.__table__.indexes
    )


def test_model_can_record_claim_and_dispatch_metadata():
    now = datetime.now(timezone.utc)
    delivery = OutboxConsumerDelivery(
        outbox_event_id=42,
        consumer_code="keycloak_projection_v1",
        status=DeliveryStatus.CLAIMING.value,
        dispatch_attempt_count=1,
        lease_owner="worker-1",
        lease_until=now,
        lease_generation=1,
        dispatched_job_id=uuid4(),
        dispatched_at=now,
    )
    assert delivery.status == "claiming"
    assert delivery.lease_owner == "worker-1"
    assert delivery.dispatched_job_id
