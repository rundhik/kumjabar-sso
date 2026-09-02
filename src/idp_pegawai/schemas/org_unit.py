from typing import Any


def serialize_org_unit(unit: Any) -> dict:
    return {
        "uuid": str(unit.uuid),
        "code": unit.code,
        "slug": unit.slug,
        "name": unit.name,
        "short_name": unit.short_name,
        "unit_type": unit.unit_type,
        "level": unit.level,
        "path": unit.path,
        "keycloak_group_path": unit.keycloak_group_path,
        "sort_order": unit.sort_order,
        "is_active": unit.is_active,
        "parent": None if unit.parent is None else {
            "uuid": str(unit.parent.uuid),
            "code": unit.parent.code,
        },
        "children_count": len(unit.children),
    }


__all__ = ["serialize_org_unit"]
