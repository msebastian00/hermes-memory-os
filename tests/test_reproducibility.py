import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_vault.py"
SNAPSHOT = ROOT / "bootstrap" / "vault-policy-snapshot"


def run_bootstrap(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, check=False)


def test_policy_snapshot_is_complete_and_hash_verified():
    result = run_bootstrap("--verify-policy-snapshot")
    assert result.returncode == 0, result.stderr
    assert "Policy snapshot verified: 7 files" in result.stdout


def test_empty_vault_bootstrap_excludes_policy_and_book_content(tmp_path):
    vault = tmp_path / "vault"
    result = run_bootstrap("--vault-root", str(vault))
    assert result.returncode == 0, result.stderr
    assert (vault / "03_RESOURCES/books").is_dir()
    assert (vault / "04_SYSTEM/policies").is_dir()
    assert not list((vault / "03_RESOURCES/books").rglob("*"))
    assert not list((vault / "04_SYSTEM/policies").glob("*.md"))


def test_policy_restore_is_hash_checked_and_never_overwrites(tmp_path):
    vault = tmp_path / "vault"
    assert run_bootstrap("--vault-root", str(vault), "--install-policy-snapshot").returncode == 0
    restored = vault / "04_SYSTEM/policies/HERMES_KNOWLEDGE_GRAPH_POLICY.md"
    source = SNAPSHOT / "04_SYSTEM/policies/HERMES_KNOWLEDGE_GRAPH_POLICY.md"
    assert hashlib.sha256(restored.read_bytes()).hexdigest() == hashlib.sha256(source.read_bytes()).hexdigest()
    restored.write_text("different live policy", encoding="utf-8")
    second = run_bootstrap("--vault-root", str(vault), "--install-policy-snapshot")
    assert second.returncode == 3
    assert restored.read_text(encoding="utf-8") == "different live policy"
