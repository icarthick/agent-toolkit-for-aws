"""current_monthly cost-anchor checks for the shared migration-report validator.

gcp-to-aws and azure-to-aws both run this validator, and each keeps its
current-spend baseline under its own key: current_costs.gcp_monthly and
current_costs.azure_monthly. The data-cost-key="current_monthly" figure must be
held to whichever of the two the estimate carries.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "validate-migration-report.py"


def _load():
    spec = importlib.util.spec_from_file_location("validate_migration_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load()


def _html(current: str | None = "$4,200/mo") -> str:
    current_cell = (
        f'<p>Current spend <span data-cost-key="current_monthly">{current}</span></p>'
        if current is not None
        else "<p>Current spend not shown.</p>"
    )
    return (
        '<section id="exec-costs">'
        f"{current_cell}"
        '<p>Balanced <strong data-cost-key="aws_monthly_balanced">$465/mo</strong></p>'
        "</section>"
    )


def _estimate(**current_costs) -> dict:
    return {
        "current_costs": {"source": "user_stated", **current_costs},
        "projected_costs": {"aws_monthly_balanced": 465.09},
    }


def _errors(html: str, estimate: dict) -> list[str]:
    return VALIDATOR._validate_cost_figures(html, estimate)


def test_azure_matching_baseline_passes() -> None:
    assert _errors(_html(), _estimate(azure_monthly=4200)) == []


def test_azure_wrong_baseline_fails() -> None:
    errors = _errors(_html("$3,900/mo"), _estimate(azure_monthly=4200))
    assert len(errors) == 1, errors
    assert 'data-cost-key="current_monthly" renders "$3900"' in errors[0]
    assert "current_costs.azure_monthly = $4200" in errors[0]


def test_azure_missing_anchor_in_exec_costs_fails() -> None:
    errors = _errors(_html(None), _estimate(azure_monthly=4200))
    assert len(errors) == 1, errors
    assert 'missing data-cost-key="current_monthly"' in errors[0]
    assert "current_costs.azure_monthly" in errors[0]


def test_azure_anchor_outside_exec_costs_does_not_satisfy_requirement() -> None:
    html = (
        '<section id="decision-summary">'
        '<span data-cost-key="current_monthly">$4,200/mo</span></section>'
        + _html(None)
    )
    errors = _errors(html, _estimate(azure_monthly=4200))
    assert len(errors) == 1, errors
    assert 'missing data-cost-key="current_monthly"' in errors[0]


def test_azure_fixture_estimate_is_held_to_azure_monthly() -> None:
    # The committed Azure estimate carries azure_monthly = 4200 and no gcp_monthly.
    fixture = (
        Path(__file__).resolve().parent.parent
        / "fixtures" / "azure-iac-terraform" / "after-estimate" / "estimation-infra.json"
    )
    estimate = json.loads(fixture.read_text(encoding="utf-8"))
    path, value, error = VALIDATOR._resolve_cost_anchor(estimate, "current_monthly")
    assert (path, value, error) == (("current_costs", "azure_monthly"), 4200, None)


def test_gcp_still_maps_to_gcp_monthly() -> None:
    html = _html("$165/mo")
    assert _errors(html, _estimate(gcp_monthly=165)) == []
    errors = _errors(_html("$999/mo"), _estimate(gcp_monthly=165))
    assert len(errors) == 1, errors
    assert "current_costs.gcp_monthly = $165" in errors[0]


def test_gcp_missing_anchor_still_fails() -> None:
    errors = _errors(_html(None), _estimate(gcp_monthly=165))
    assert len(errors) == 1, errors
    assert "current_costs.gcp_monthly" in errors[0]


def test_no_baseline_skips_current_monthly() -> None:
    # Neither key set (or set to null): nothing to assert and nothing to require.
    assert _errors(_html(None), _estimate()) == []
    assert _errors(_html(None), _estimate(gcp_monthly=None)) == []
    assert _errors(_html("$1/mo"), _estimate(azure_monthly=None)) == []


def test_both_baselines_present_is_ambiguous() -> None:
    errors = _errors(_html(), _estimate(gcp_monthly=165, azure_monthly=4200))
    assert len(errors) == 1, errors
    assert "more than one figure" in errors[0]
    assert "current_costs.gcp_monthly" in errors[0]
    assert "current_costs.azure_monthly" in errors[0]
