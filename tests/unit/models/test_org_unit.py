from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import inspect

from idp_pegawai.models.base import Base, TimestampMixin, UUIDMixin, SoftDeleteMixin
from idp_pegawai.models.org_unit import OrgUnit


def test_shared_mixins_define_identity_audit_and_soft_delete_columns():
    columns = {column.name for column in inspect(OrgUnit).columns}
    assert {"id", "uuid", "created_at", "updated_at", "deleted_at", "metadata"} <= columns
    assert inspect(OrgUnit).columns.id.primary_key
    assert inspect(OrgUnit).columns.uuid.unique
    assert issubclass(OrgUnit, Base)


def test_valid_root_and_child_have_hierarchy_relationship_and_defaults():
    root = OrgUnit(code="KW", slug="kanwil", name="Kanwil", unit_type="kanwil", level=0, path="/KW", keycloak_group_path="/pegawai/KW")
    child = OrgUnit(code="DIV", slug="divisi", name="Divisi", unit_type="divisi", level=1, path="/KW/DIV", keycloak_group_path="/pegawai/KW/DIV", parent=root)
    assert child.parent is root
    assert child in root.children
    assert root.level == 0 and root.sort_order == 0 and root.is_active is True
    assert isinstance(root.uuid, UUID)


@pytest.mark.parametrize("kwargs", [
    {"level": -1},
    {"unit_type": "invalid"},
    {"path": "relative"},
    {"keycloak_group_path": "/other/x"},
])
def test_invalid_hierarchy_values_are_rejected(kwargs):
    values = dict(code="A", slug="a", name="A", unit_type="kanwil", level=0, path="/A", keycloak_group_path="/pegawai/A")
    values.update(kwargs)
    with pytest.raises(ValueError):
        OrgUnit(**values)


def test_effective_date_range_and_active_state_are_validated():
    with pytest.raises(ValueError):
        OrgUnit(code="A", slug="a", name="A", unit_type="kanwil", level=0, path="/A", keycloak_group_path="/pegawai/A", effective_from=date(2026, 2, 1), effective_to=date(2026, 1, 1))
    with pytest.raises(ValueError):
        OrgUnit(code="A", slug="a", name="A", unit_type="kanwil", level=0, path="/A", keycloak_group_path="/pegawai/A", is_active=False, effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31))


def test_parent_cycle_is_rejected():
    root = OrgUnit(code="A", slug="a", name="A", unit_type="kanwil", level=0, path="/A", keycloak_group_path="/pegawai/A")
    child = OrgUnit(code="B", slug="b", name="B", unit_type="divisi", level=1, path="/A/B", keycloak_group_path="/pegawai/A/B", parent=root)
    with pytest.raises(ValueError):
        root.parent = child


def test_metadata_is_json_mapping():
    unit = OrgUnit(code="A", slug="a", name="A", unit_type="kanwil", level=0, path="/A", keycloak_group_path="/pegawai/A")
    assert unit.metadata == {}
    assert isinstance(inspect(OrgUnit).columns.metadata.type.python_type, type)


def test_model_metadata_is_shared_for_alembic():
    assert Base.metadata is OrgUnit.metadata
    assert OrgUnit.__tablename__ == "org_units"


def test_timestamp_mixins_are_available():
    assert TimestampMixin and UUIDMixin and SoftDeleteMixin
    assert OrgUnit().created_at is None
    assert OrgUnit().updated_at is None
