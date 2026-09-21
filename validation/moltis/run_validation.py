#!/usr/bin/env python3
"""Reproduce against unmodified Moltis runtime sources; only loopback synthetic I/O."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

HEAD = "9d3238c322708e9d57fe235ce1c2b43ccc33af62"
BASE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--cargo", type=Path, required=True, help="Absolute cargo binary from an installed toolchain")
    parser.add_argument("--cargo-home", type=Path, required=True, help="Dependency cache, never a credentials file")
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch-dir", type=Path, default=Path("/private/tmp" if Path("/private/tmp").is_dir() else "/tmp"))
    parser.add_argument("--fetch-dependencies", action="store_true", help="Permit cargo to download public locked dependencies before offline tests")
    args = parser.parse_args()
    repo = args.checkout.resolve()
    cargo = args.cargo.resolve()
    output = args.output.resolve()
    if os.name != "posix":
        raise SystemExit("This runner currently supports POSIX hosts only; Windows is unverified")
    if cargo.name == "rustup" or not cargo.is_file() or not (cargo.parent / "rustc").is_file():
        raise SystemExit("Use a real toolchain cargo binary with sibling rustc, not a rustup shim")
    args.scratch_dir = args.scratch_dir.resolve()
    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if head != HEAD:
        raise SystemExit(f"Expected upstream {HEAD}; actual {head}; re-review a different revision first")
    # Never overwrite tracked or unrelated work in a caller's checkout.
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", "crates", "Cargo.toml", "Cargo.lock"], cwd=repo, check=True)
    copies = {
        BASE / "baizhi_loopback.rs": "crates/mcp-agent-bridge/tests/baizhi_loopback.rs",
        BASE / "baizhi_guide_config.rs": "crates/config/tests/baizhi_guide_config.rs",
        BASE / "moltis-baizhi.toml": "crates/config/tests/fixtures/baizhi-guide.toml",
    }
    for source, relative in copies.items():
        target = repo / relative
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise SystemExit(f"Refusing to overwrite different file: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    lock_before = hashlib.sha256((repo / "Cargo.lock").read_bytes()).hexdigest()
    results = []
    with tempfile.TemporaryDirectory(prefix="moltis-synthetic-", dir=args.scratch_dir) as state:
        state = Path(state)
        for name in ("config", "data"):
            (state / name).mkdir()
        # Construct a fresh environment. No inherited model keys, user HOME, proxy,
        # OAuth token store, BAIZHI credentials, or user Moltis config is available.
        env = {
            "PATH": str(cargo.parent) + os.pathsep + "/usr/bin:/bin:/usr/sbin:/sbin",
            "CARGO_HOME": str(args.cargo_home.resolve()),
            "CARGO_TARGET_DIR": str(args.target_dir.resolve()),
            "MOLTIS_FIXTURE_ROOT": str(state.resolve()),
            "MOLTIS_CONFIG_DIR": str(state / "config"),
            "MOLTIS_DATA_DIR": str(state / "data"),
            "BAIZHI_API_KEY": "synthetic-ambient-value-must-not-be-used",
        }
        commands = []
        if args.fetch_dependencies:
            commands.append(("build-public-dependencies", [str(cargo), "test", "-p", "moltis-mcp-agent-bridge", "--test", "baizhi_loopback", "--locked", "--no-run"]))
        for package, target in [("moltis-mcp-agent-bridge", "baizhi_loopback"), ("moltis-config", "baizhi_guide_config")]:
            commands.append((target, [str(cargo), "test", "-p", package, "--test", target, "--locked", "--offline", "--", "--nocapture"]))
        for label, command in commands:
            with (output / (label + ".log")).open("w", encoding="utf-8") as log:
                result = subprocess.run(command, cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT)
            results.append({"name": label, "command": command, "exit_code": result.returncode})
            print(f"{label}: exit {result.returncode}")
            if result.returncode:
                break
        runtime = {}
        for binary in (cargo, cargo.parent / "rustc"):
            runtime[binary.name] = subprocess.check_output([str(binary), "--version"], env=env, text=True).strip()
    lock_after = hashlib.sha256((repo / "Cargo.lock").read_bytes()).hexdigest()
    record = {"at": datetime.now(timezone.utc).isoformat(), "head": head, "runtime": runtime,
              "lock_sha256_before": lock_before, "lock_sha256_after": lock_after,
              "production_calls": 0, "real_credentials_used": False, "commands": results,
              "fixture_scope": "native MCP manager, client, bridge, sync_mcp_tools and ToolRegistry; synthetic loopback HTTP server; no model/UI/gateway auth"}
    (output / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if lock_before != lock_after:
        raise SystemExit("Cargo.lock changed")
    if any(item["exit_code"] for item in results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
