"""Build an in-memory import plan; this module deliberately has no database writes."""
from dataclasses import dataclass, field
from typing import Any, Iterable
from .validation import ValidationResult

@dataclass(frozen=True)
class PlanItem:
    row_number: int
    operation: str
    nip: str | None
    candidate: dict[str, Any]

@dataclass
class DryRunPlan:
    items: list[PlanItem] = field(default_factory=list)
    validation: ValidationResult | None = None
    @property
    def blocked(self): return bool(self.validation and self.validation.blocking)
    @property
    def summary(self):
        return {op: sum(i.operation == op for i in self.items) for op in ("planned_create", "planned_update", "planned_noop", "planned_reject")}

def build_dry_run_plan(rows: Iterable[dict[str, Any]], existing: dict[str, dict[str, Any]] | None = None, validation: ValidationResult | None = None) -> DryRunPlan:
    """Compare rows to an authoritative snapshot without mutating it."""
    existing = existing or {}
    plan = DryRunPlan(validation=validation)
    issues_by_row = {}
    if validation:
        for issue in validation.issues:
            if issue.row_number: issues_by_row.setdefault(issue.row_number, []).append(issue)
    for number, row in enumerate(rows, 1):
        nip = row.get("nip")
        candidate = {k: getattr(v, "normalized", v) for k, v in row.items()}
        if any(i.severity in {"error", "fatal"} for i in issues_by_row.get(number, [])):
            operation = "planned_reject"
        elif nip not in existing:
            operation = "planned_create"
        elif candidate == existing[nip]:
            operation = "planned_noop"
        else:
            operation = "planned_update"
        plan.items.append(PlanItem(number, operation, nip, candidate))
    return plan

__all__ = ["PlanItem", "DryRunPlan", "build_dry_run_plan"]
