#!/usr/bin/env python3
"""Create an empty vault layout and optionally restore the policy snapshot safely."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT = REPO_ROOT / "bootstrap" / "vault-layout.txt"
SNAPSHOT_ROOT = REPO_ROOT / "bootstrap" / "vault-policy-snapshot"
MANIFEST = SNAPSHOT_ROOT / "manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe relative path: {value}")
    return path


def layout_paths() -> list[Path]:
    return [relative_path(line.strip()) for line in LAYOUT.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


def policy_files() -> list[dict[str, str]]:
    return list(json.loads(MANIFEST.read_text(encoding="utf-8"))["files"])


def verify_snapshot() -> list[str]:
    errors: list[str] = []
    for item in policy_files():
        relative = relative_path(item["path"])
        source = SNAPSHOT_ROOT / relative
        if not source.is_file():
            errors.append(f"missing snapshot file: {relative}")
        elif sha256(source) != item["sha256"]:
            errors.append(f"snapshot hash mismatch: {relative}")
    return errors


def bootstrap(vault_root: Path, *, install_policies: bool, dry_run: bool) -> int:
    errors = verify_snapshot()
    if errors:
        print("Snapshot verification failed:\n" + "\n".join(errors), file=sys.stderr)
        return 2
    conflicts = []
    if install_policies:
        for item in policy_files():
            destination = vault_root / relative_path(item["path"])
            if destination.exists() and sha256(destination) != item["sha256"]:
                conflicts.append(str(destination.relative_to(vault_root)))
    if conflicts:
        print("Refusing to overwrite different live policy files:\n" + "\n".join(conflicts), file=sys.stderr)
        return 3
    for relative in layout_paths():
        destination = vault_root / relative
        print(f"{'would create' if dry_run else 'create'} directory {destination}")
        if not dry_run:
            destination.mkdir(parents=True, exist_ok=True)
    if install_policies:
        for item in policy_files():
            relative = relative_path(item["path"])
            source, destination = SNAPSHOT_ROOT / relative, vault_root / relative
            if destination.exists():
                print(f"keep matching policy {destination}")
            else:
                print(f"{'would restore' if dry_run else 'restore'} policy {destination}")
                if not dry_run:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
    print("Vault bootstrap complete. No books, notes, queues, generated content, credentials, or database data were copied.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", type=Path, help="Destination vault directory")
    parser.add_argument("--install-policy-snapshot", action="store_true", help="Restore only matching-or-missing policy files")
    parser.add_argument("--dry-run", action="store_true", help="Print planned filesystem changes")
    parser.add_argument("--verify-policy-snapshot", action="store_true", help="Verify committed policy snapshot hashes and exit")
    args = parser.parse_args()
    if args.verify_policy_snapshot:
        errors = verify_snapshot()
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 2
        print(f"Policy snapshot verified: {len(policy_files())} files")
        return 0
    if args.vault_root is None:
        parser.error("--vault-root is required unless --verify-policy-snapshot is used")
    return bootstrap(args.vault_root, install_policies=args.install_policy_snapshot, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
