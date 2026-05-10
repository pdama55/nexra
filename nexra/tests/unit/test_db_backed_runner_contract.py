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


def test_runner_loads_env_files_and_skips_docker_for_external_targets() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert '".env.local"' in source
    assert '"nexra" / ".env"' in source
    assert "key.startswith(\"export \")" in source
    assert "external endpoints are configured; skipping docker fallback in auto mode" in source
