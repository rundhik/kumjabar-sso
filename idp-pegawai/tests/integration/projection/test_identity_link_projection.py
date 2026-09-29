from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from idp_pegawai.models.base import Base
from idp_pegawai.models.identity_link import PegawaiIdentityLink
from idp_pegawai.projection.identity_links import IdentityLinkConflict, project_identity_link


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    PegawaiIdentityLink.__table__.create(engine)
    with Session(engine) as value:
        yield value


def event(aggregate_uuid, *, version=1, subject=None, correlation=None):
    return {
        "aggregate_uuid": str(aggregate_uuid), "source_version": version,
        "correlation_uuid": str(correlation or uuid4()),
        "provider": "keycloak", "provider_subject": str(subject or uuid4()),
        "management_mode": "idp_managed", "link_status": "linked",
    }


def test_projection_correlates_by_uuid_and_never_hard_deletes(session):
    pegawai_uuid, subject = uuid4(), uuid4()
    record = project_identity_link(session, event(pegawai_uuid, subject=subject))
    assert record.uuid == pegawai_uuid
    assert record.provider_subject == str(subject)
    assert record.correlation_uuid is not None
    assert session.get(PegawaiIdentityLink, record.id) is not None


def test_stale_event_is_noop(session):
    aggregate_uuid = uuid4()
    current = project_identity_link(session, event(aggregate_uuid, version=3))
    stale = project_identity_link(session, event(aggregate_uuid, version=2))
    assert stale is current
    assert current.link_version == 3


def test_identity_link_conflict_fails_closed(session):
    aggregate_uuid = uuid4()
    subject = uuid4()
    project_identity_link(session, event(uuid4(), subject=subject))
    with pytest.raises(IdentityLinkConflict):
        project_identity_link(session, event(aggregate_uuid, subject=subject))
    assert session.query(PegawaiIdentityLink).filter_by(link_status="blocked").count() == 1


def test_unlink_is_tombstone_not_delete(session):
    aggregate_uuid = uuid4()
    record = project_identity_link(session, event(aggregate_uuid))
    result = project_identity_link(session, {**event(aggregate_uuid, version=2), "link_status": "unlinked"})
    assert result is record
    assert record.link_status == "unlinked"
    assert session.query(PegawaiIdentityLink).count() == 1
    assert record.unlinked_at is not None
