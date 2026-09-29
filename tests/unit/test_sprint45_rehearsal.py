"""Sprint 4–5 local rehearsal contracts; fixtures are synthetic only."""
from dataclasses import dataclass
from pathlib import Path

import yaml

from idp_pegawai.consumer.bootstrap import BootstrapCoordinator
from idp_pegawai.consumer.projector import project_snapshot


@dataclass
class Row:
    change_sequence: int


def test_staging_keycloak_artifact_is_pinned_and_not_dev_mode():
    path = Path(__file__).parents[2] / "deploy/keycloak-compose.staging.yml"
    compose = yaml.safe_load(path.read_text())
    service = compose["services"]["kumjabar_keycloak_staging"]
    assert service["image"].rsplit(":", 1)[1] == "26.7.3"
    assert "start-dev" not in service["command"]
    assert service["environment"]["KC_HTTP_ENABLED"] if "KC_HTTP_ENABLED" in service["environment"] else True


def test_bootstrap_cutoff_then_new_row_is_delta_rehearsal():
    rows = [Row(1), Row(2)]
    coordinator = BootstrapCoordinator(rows=rows, capture_cutoff=lambda: 2)
    session = coordinator.start(page_size=10)
    assert [row.change_sequence for row in session.page().items] == [1, 2]
    rows.append(Row(3))
    assert session.cutoff_sequence == 2


def test_projection_replay_is_deterministic_and_conflict_changes_hash():
    source = {"pegawai_uuid": "ABC", "nip": "ignored", "nama": "ignored", "status_pegawai": "active"}
    first = project_snapshot("pegawai", "pegawai.portal-minimal.v1", source, source_version=4)
    replay = project_snapshot("pegawai", "pegawai.portal-minimal.v1", source, source_version=4)
    conflict = project_snapshot("pegawai", "pegawai.portal-minimal.v1", {**source, "status_pegawai": "suspended"}, source_version=5)
    assert first == replay
    assert conflict["payload_hash"] != first["payload_hash"]
    assert first["resource_uuid"] == "abc"


def test_suspension_and_reactivation_are_explicit_snapshot_states():
    base = {"pegawai_uuid": "abc", "status_pegawai": "active"}
    suspended = project_snapshot("pegawai", "pegawai.portal-minimal.v1", {**base, "status_pegawai": "suspended"})
    active = project_snapshot("pegawai", "pegawai.portal-minimal.v1", base)
    assert suspended["data"]["status_pegawai"] == "suspended"
    assert active["data"]["status_pegawai"] == "active"
    assert suspended["payload_hash"] != active["payload_hash"]
