from datetime import datetime, timedelta, timezone

import pytest

from idp_pegawai.workers.delivery import (
    DeliveryStatus,
    FencingError,
    InMemoryDeliveryStore,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_delivery_is_idempotent_per_consumer():
    store = InMemoryDeliveryStore()

    first = store.enqueue("event-1", "keycloak_projection_v1")
    duplicate = store.enqueue("event-1", "keycloak_projection_v1")
    other_consumer = store.enqueue("event-1", "consumer-b")

    assert duplicate.id == first.id
    assert other_consumer.id != first.id
    assert len(store) == 2


def test_claim_uses_fencing_token_and_stale_owner_cannot_finalize():
    store = InMemoryDeliveryStore(lease_duration=timedelta(seconds=10))
    store.enqueue("event-1", "consumer-a")

    first = store.claim("worker-a", now=NOW)
    assert first.status is DeliveryStatus.CLAIMING
    assert first.lease_generation == 1

    reclaimed = store.claim("worker-b", now=NOW + timedelta(seconds=11))
    assert reclaimed.lease_generation == 2

    with pytest.raises(FencingError):
        store.complete(first.id, first.fencing_token, now=NOW + timedelta(seconds=11))

    done = store.complete(reclaimed.id, reclaimed.fencing_token, now=NOW + timedelta(seconds=11))
    assert done.status is DeliveryStatus.DISPATCHED


def test_transient_failures_retry_then_dead_letter():
    store = InMemoryDeliveryStore(max_attempts=3, retry_delay=lambda attempt: timedelta(seconds=attempt))
    store.enqueue("event-1", "consumer-a")

    claimed = store.claim("worker", now=NOW)
    retry = store.fail(claimed.id, claimed.fencing_token, retryable=True, now=NOW)
    assert retry.status is DeliveryStatus.RETRY_WAIT
    assert retry.dispatch_attempt_count == 1
    assert retry.next_dispatch_at == NOW + timedelta(seconds=1)

    claimed = store.claim("worker", now=retry.next_dispatch_at)
    retry = store.fail(claimed.id, claimed.fencing_token, retryable=True, now=retry.next_dispatch_at)
    claimed = store.claim("worker", now=retry.next_dispatch_at)
    dead = store.fail(claimed.id, claimed.fencing_token, retryable=True, now=retry.next_dispatch_at)

    assert dead.status is DeliveryStatus.DEAD_LETTER
    assert dead.dispatch_attempt_count == 3


def test_non_retryable_failure_goes_directly_to_dead_letter():
    store = InMemoryDeliveryStore()
    store.enqueue("event-1", "consumer-a")
    claimed = store.claim("worker", now=NOW)

    dead = store.fail(claimed.id, claimed.fencing_token, retryable=False, error_code="invalid_payload", now=NOW)

    assert dead.status is DeliveryStatus.DEAD_LETTER
    assert dead.last_error_code == "invalid_payload"


def test_expired_claim_is_recoverable():
    store = InMemoryDeliveryStore(lease_duration=timedelta(seconds=10))
    store.enqueue("event-1", "consumer-a")
    store.claim("worker", now=NOW)

    recovered = store.recover_expired(now=NOW + timedelta(seconds=11))
    assert recovered == 1
    assert store.get("event-1", "consumer-a").status is DeliveryStatus.PENDING
