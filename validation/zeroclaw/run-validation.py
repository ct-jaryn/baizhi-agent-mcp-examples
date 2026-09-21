#!/usr/bin/env python3
"""Run six ZeroClaw checks without contacting Baizhi or inheriting API keys."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE_SHA = "fba46e349b6bd084d43b721c7645525d2f5c597d"
# These were local docs-only candidates, not public upstream revisions.
DOCS_ONLY_HEADS = {
    "0d068563166b97976dcedc44fc07f5a316166fca",
    "e873b962b7e9879e9dfb0cd12b3f7a6b5b22da57",
}
LOCK_SHA256 = "00fa81d479a80d61823840ed4ee6d1c157a1db6536fb391a71169fcd6f6d0509"
HERE = Path(__file__).resolve().parent
GUIDE = HERE.parent.parent / "guides" / "zeroclaw.md"


def git(checkout: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args], text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--cargo", default="cargo", help="Cargo executable or absolute path")
    parser.add_argument("--cargo-home", type=Path, help="Optional dependency cache; use a dedicated cache")
    parser.add_argument("--target-dir", type=Path, help="Optional separate build cache")
    parser.add_argument("--offline", action="store_true", help="Require already cached dependencies")
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    if Path(git(checkout, "rev-parse", "--show-toplevel")).resolve() != checkout:
        parser.error("--checkout must be the repository root")
    head = git(checkout, "rev-parse", "HEAD")
    if head not in {BASE_SHA, *DOCS_ONLY_HEADS}:
        parser.error(f"checkout must be pinned to {BASE_SHA}; no automatic checkout is performed")
    if git(checkout, "status", "--porcelain"):
        parser.error("use a clean, dedicated checkout; no existing changes will be overwritten")
    if head in DOCS_ONLY_HEADS:
        changed = git(checkout, "diff", "--name-only", BASE_SHA, head).splitlines()
        if changed != ["docs/book/src/tools/mcp.md"]:
            parser.error("known local candidate must differ from base only in the MCP documentation")
    lock = checkout / "Cargo.lock"
    if hashlib.sha256(lock.read_bytes()).hexdigest() != LOCK_SHA256:
        parser.error("Cargo.lock does not match the validated source snapshot")
    cargo = shutil.which(args.cargo)
    if cargo is None:
        parser.error("Cargo not found; install the documented Rust toolchain first")
    cargo_path = Path(cargo).absolute()
    test_dir = checkout / "crates" / "zeroclaw-tools" / "tests"
    destinations = [test_dir / "baizhi_mcp_guide.rs", test_dir / "baizhi_mcp_guide.md"]
    if any(p.exists() or p.is_symlink() for p in destinations):
        parser.error("validation destination already exists; refusing to replace it")

    with tempfile.TemporaryDirectory(prefix="baizhi-zeroclaw-check-") as tmp:
        work = Path(tmp)
        cargo_home = (args.cargo_home or work / "cargo-home").resolve()
        target_dir = (args.target_dir or work / "target").resolve()
        cargo_home.mkdir(parents=True, exist_ok=True)
        target_dir.mkdir(parents=True, exist_ok=True)
        # Do not forward Baizhi/model keys, proxy credentials, or ZEROCLAW_* overrides.
        env = {
            "PATH": str(cargo_path.parent) + os.pathsep + os.environ.get("PATH", os.defpath),
            "CARGO_HOME": str(cargo_home),
            "CARGO_TARGET_DIR": str(target_dir),
            "CARGO_BUILD_JOBS": "2",
            "CARGO_PROFILE_DEV_DEBUG": "0",
            "CARGO_PROFILE_TEST_DEBUG": "0",
        }
        # Toolchain and locale paths only; these are not service credentials.
        for key in ("RUSTUP_HOME", "DYLD_LIBRARY_PATH", "LANG", "LC_ALL", "SYSTEMROOT"):
            if key in os.environ:
                env[key] = os.environ[key]
        print(f"ZeroClaw source HEAD: {head}", flush=True)
        print(f"Pinned runtime base: {BASE_SHA}", flush=True)
        subprocess.run([str(cargo_path), "--version"], env=env, check=True)
        subprocess.run(["rustc", "--version"], env=env, check=True)
        test_dir.mkdir(exist_ok=True)
        created: list[Path] = []
        try:
            for src, dst in zip([HERE / "baizhi_mcp_guide.rs", GUIDE], destinations):
                with dst.open("xb") as output:
                    created.append(dst)
                    output.write(src.read_bytes())
            command = [str(cargo_path), "test", "--locked"]
            if args.offline:
                command.append("--offline")
            command += ["-p", "zeroclaw-tools", "--test", "baizhi_mcp_guide", "--", "--test-threads=1"]
            return subprocess.run(command, cwd=checkout, env=env, check=False).returncode
        finally:
            for path in created:
                path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
