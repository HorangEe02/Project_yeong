from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "setup_host_ollama.sh"


def test_setup_host_ollama_check_only_accepts_models_root(tmp_path):
    models = tmp_path / "models"
    (models / "blobs").mkdir(parents=True)
    (models / "manifests").mkdir()

    result = subprocess.run(
        ["bash", str(SCRIPT), "--check-only", "--models-root", str(models)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0
    assert "Model root:" in result.stdout


def test_setup_host_ollama_rejects_manifest_leaf(tmp_path):
    leaf = tmp_path / "models" / "manifests" / "registry.ollama.ai" / "library"
    leaf.mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--check-only", "--models-root", str(leaf)],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode != 0
    assert "parent models root" in result.stderr
