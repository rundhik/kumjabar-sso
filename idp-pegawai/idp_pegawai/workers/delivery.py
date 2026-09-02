"""In-memory per-consumer outbox delivery state machine.

Persistence and remote execution are deliberately outside this first slice.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable
from uuid import uuid4


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    CLAIMING = "claiming"
    DISPATCHED = "dispatched"
    RETRY_WAIT = "retry_wait"
    BLOCKED = "blocked"
    DEAD_LETTER = "dead_letter"


class FencingError(RuntimeError):
    """The lease owner or fencing token is stale."""


@dataclass(frozen=True)
class Delivery:
    id: str
    outbox_event_id: str
    consumer_code: str
    status: DeliveryStatus = DeliveryStatus.PENDING
    dispatch_attempt_count: int = 0
    next_dispatch_at: datetime | None = None
    lease_owner: str | None = None
    lease_until: datetime | None = None
    lease_generation: int = 0
    last_error_code: str | None = None
    fencing_token: int = 0


class InMemoryDeliveryStore:
    def __init__(self, *, lease_duration=timedelta(minutes=5), max_attempts=8,
                 retry_delay: Callable[[int], timedelta] | None = None):
        self.lease_duration = lease_duration
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay or (lambda attempt: timedelta(seconds=2**attempt))
        self._deliveries: dict[tuple[str, str], Delivery] = {}

    def __len__(self):
        return len(self._deliveries)

    def enqueue(self, outbox_event_id: str, consumer_code: str) -> Delivery:
        key = (outbox_event_id, consumer_code)
        delivery = self._deliveries.get(key)
        if delivery is None:
            delivery = Delivery(str(uuid4()), outbox_event_id, consumer_code)
            self._deliveries[key] = delivery
        return delivery

    def get(self, outbox_event_id: str, consumer_code: str) -> Delivery:
        return self._deliveries[(outbox_event_id, consumer_code)]

    def claim(self, owner: str, *, now: datetime | None = None) -> Delivery:
        now = now or datetime.now(timezone.utc)
        for key, current in self._deliveries.items():
            due = current.next_dispatch_at is None or current.next_dispatch_at <= now
            available = current.status is DeliveryStatus.PENDING or (
                current.status is DeliveryStatus.RETRY_WAIT and due)
            expired = current.status is DeliveryStatus.CLAIMING and current.lease_until is not None and current.lease_until <= now
            if available or expired:
                claimed = replace(current, status=DeliveryStatus.CLAIMING,
                    lease_owner=owner, lease_until=now + self.lease_duration,
                    lease_generation=current.lease_generation + 1,
                    fencing_token=current.fencing_token + 1,
                    dispatch_attempt_count=current.dispatch_attempt_count + 1,
                    next_dispatch_at=None)
                self._deliveries[key] = claimed
                return claimed
        raise LookupError("no delivery available")

    def _fenced(self, delivery_id, token):
        current = next((d for d in self._deliveries.values() if d.id == delivery_id), None)
        if current is None or current.status is not DeliveryStatus.CLAIMING or current.fencing_token != token:
            raise FencingError("stale delivery lease")
        return current

    def complete(self, delivery_id, fencing_token, *, now=None):
        current = self._fenced(delivery_id, fencing_token)
        updated = replace(current, status=DeliveryStatus.DISPATCHED, lease_owner=None, lease_until=None)
        self._deliveries[(current.outbox_event_id, current.consumer_code)] = updated
        return updated

    def fail(self, delivery_id, fencing_token, *, retryable, error_code="delivery_failed", now=None):
        now = now or datetime.now(timezone.utc)
        current = self._fenced(delivery_id, fencing_token)
        terminal = not retryable or current.dispatch_attempt_count >= self.max_attempts
        updated = replace(current, status=DeliveryStatus.DEAD_LETTER if terminal else DeliveryStatus.RETRY_WAIT,
            next_dispatch_at=None if terminal else now + self.retry_delay(current.dispatch_attempt_count),
            last_error_code=error_code, lease_owner=None, lease_until=None)
        self._deliveries[(current.outbox_event_id, current.consumer_code)] = updated
        return updated

    def recover_expired(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        count = 0
        for key, current in list(self._deliveries.items()):
            if current.status is DeliveryStatus.CLAIMING and current.lease_until is not None and current.lease_until <= now:
                self._deliveries[key] = replace(current, status=DeliveryStatus.PENDING, lease_owner=None, lease_until=None)
                count += 1
        return count
