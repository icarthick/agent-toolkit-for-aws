"""The report validators share helpers through skills/shared/report/.

Each skill installs on its own, so a validator must find the helper module from
its own skill folder. The gcp-to-aws validator prefers the canonical file in the
plugin source tree; the Heroku validator reads only its skill's vendored copy.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess  # nosec B404 — test-only, list args, no shell, committed script paths
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HELPERS = Path("report") / "report_validator_helpers.py"
CANONICAL = PLUGIN_ROOT / "skills" / "shared" / HELPERS
GCP_VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-migration-report.py"
HEROKU_SKILL = PLUGIN_ROOT / "skills" / "heroku-to-aws"
HEROKU_VALIDATOR_NAME = "validate-heroku-migration-report.py"
HEROKU_DECISION_RUN = PLUGIN_ROOT / "fixtures" / "heroku-decision-gate" / "after-decide-complete"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _isolated_heroku_skill(tmp_path: Path) -> Path:
    """A copy of skills/heroku-to-aws/ alone, with no plugin tree around it."""
    skill = tmp_path / "installed" / "heroku-to-aws"
    shutil.copytree(HEROKU_SKILL, skill, ignore=shutil.ignore_patterns("__pycache__"))
    return skill


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603
        [sys.executable, *args], cwd=cwd, capture_output=True, text=True
    )


def test_heroku_validator_runs_from_its_skill_directory_alone(tmp_path):
    skill = _isolated_heroku_skill(tmp_path)
    validator = skill / "scripts" / HEROKU_VALIDATOR_NAME
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert not (tmp_path / "installed" / "shared").exists()

    help_result = _run([str(validator), "--help"], elsewhere)
    assert help_result.returncode == 0, help_result.stderr
    assert "usage:" in help_result.stdout

    run_dir = tmp_path / "run"
    shutil.copytree(HEROKU_DECISION_RUN, run_dir)
    report = _run(
        [str(validator), str(run_dir / "decision-report.html"),
         "--migration-dir", str(run_dir), "--mode", "decision"],
        elsewhere,
    )
    assert report.returncode == 0, report.stdout + report.stderr
    assert "REPORT_OK" in report.stdout

    # The vendored directory is parity-checked: running the validator must not
    # leave a bytecode cache next to the copy.
    assert not list((skill / "references" / "vendored").rglob("__pycache__"))


def test_heroku_validator_needs_its_vendored_copy(tmp_path):
    skill = _isolated_heroku_skill(tmp_path)
    (skill / "references" / "vendored" / HELPERS).unlink()
    result = _run([str(skill / "scripts" / HEROKU_VALIDATOR_NAME), "--help"], tmp_path)
    assert result.returncode != 0
    assert "report_validator_helpers.py" in result.stderr


def test_gcp_validator_uses_the_canonical_file_in_the_source_tree():
    module = _load("_shared_helpers_gcp_source", GCP_VALIDATOR)
    assert Path(module._report_helpers.__file__) == CANONICAL


def test_gcp_validator_uses_the_vendored_copy_in_a_skill_folder(tmp_path):
    skill = tmp_path / "skills" / "gcp-to-aws"
    (skill / "scripts").mkdir(parents=True)
    shutil.copy2(GCP_VALIDATOR, skill / "scripts" / GCP_VALIDATOR.name)
    vendored = skill / "references" / "vendored" / HELPERS
    vendored.parent.mkdir(parents=True)
    shutil.copy2(CANONICAL, vendored)
    module = _load("_shared_helpers_gcp_packaged", skill / "scripts" / GCP_VALIDATOR.name)
    assert Path(module._report_helpers.__file__) == vendored


def test_each_validator_keeps_its_own_phrase_matcher():
    gcp = _load("_shared_helpers_gcp_matcher", GCP_VALIDATOR)
    heroku = _load("_shared_helpers_heroku_matcher", HEROKU_SKILL / "scripts" / HEROKU_VALIDATOR_NAME)
    # GCP reads the phrase as HTML visible text, so the hidden span drops out and
    # "confirm capacity" matches. Heroku only folds dashes and whitespace, so the
    # markup words stay in the phrase and nothing matches.
    phrases = ['<span hidden>internal note</span> Confirm capacity']
    items = ["confirm capacity"]
    assert gcp._unmatched_phrases(phrases, items, gcp._phrase_rendered) == []
    assert heroku._unmatched_phrases(phrases, items, heroku._phrase_rendered) == phrases
