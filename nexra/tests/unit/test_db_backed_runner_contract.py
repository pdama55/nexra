from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts" / "run_db_backed_tests.sh"


def test_runner_emits_explicit_precheck_classifications() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "db_precheck=failed classification=" in source
    assert "redis_precheck=failed classification=" in source
    assert "credential_or_config_failure" in source
    assert "docker_daemon_unavailable" in source
