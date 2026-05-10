from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRANCH_PROTECTION_GATE = ROOT / "scripts" / "branch_protection_gate.sh"
CONVERGENCE = ROOT / "scripts" / "validate_convergence.sh"


def test_branch_protection_gate_script_exists_and_writes_evidence() -> None:
    source = BRANCH_PROTECTION_GATE.read_text(encoding="utf-8")
    assert "branch_protection_status.json" in source
    assert "blocked_by_plan" in source
    assert "configured_but_incomplete" in source


def test_convergence_runner_references_branch_protection_gate() -> None:
    source = CONVERGENCE.read_text(encoding="utf-8")
    assert "branch_protection_gate.sh" in source
