#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run native OpenHuman checks with synthetic loopback MCP peers (macOS)."""

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import platform
import subprocess

BASE = "eb4fdc0f4f4a036d8ab7c12bd52f16128e4a6b5d"
TARGET = "baizhi_mcp_loopback"
DECL = '\n[[test]]\nname = "baizhi_mcp_loopback"\npath = "../../tests/baizhi_mcp_loopback.rs"\nrequired-features = ["mcp"]\n'
POLICY = '(version 1) (allow default) (deny network*) (allow network-inbound (local ip "localhost:*")) (allow network-outbound (remote ip "localhost:*"))'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, type=pathlib.Path)
    ap.add_argument(
        "--cargo",
        required=True,
        type=pathlib.Path,
        help="Actual cargo binary alongside rustc, not an unconfigured rustup shim",
    )
    ap.add_argument("--cargo-home", required=True, type=pathlib.Path)
    ap.add_argument("--out-dir", required=True, type=pathlib.Path)
    ap.add_argument(
        "--download-deps",
        action="store_true",
        help="Permit dependency downloads during compilation only",
    )
    args = ap.parse_args()
    repo = args.repo.resolve()
    cargo = args.cargo.resolve()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (
        platform.system() != "Darwin"
        or not pathlib.Path("/usr/bin/sandbox-exec").exists()
    ):
        raise SystemExit(
            "This verified runner requires macOS sandbox-exec to deny non-loopback network. Other platforms need equivalent isolation; no unprotected fallback is provided."
        )
    if git(repo, "rev-parse", "HEAD") != BASE:
        raise SystemExit("Use the documented exact upstream commit.")
    submodules = subprocess.check_output(
        ["git", "submodule", "status", "--recursive"], cwd=repo, text=True
    )
    if not submodules.strip() or any(
        line[:1] != " " for line in submodules.splitlines()
    ):
        raise SystemExit(
            "Initialize every recursive submodule at its recorded gitlink; no altered submodule heads."
        )
    source_status = {"root": git(repo, "status", "--porcelain")}
    for line in submodules.splitlines():
        subpath = line[42:].rsplit(" (", 1)[0]
        source_status[subpath] = git(repo / subpath, "status", "--porcelain")
    if any(source_status.values()):
        raise SystemExit(
            "Use a clean isolated checkout including every recursive submodule; tracked or untracked source changes are not accepted."
        )
    source = pathlib.Path(__file__).with_name(TARGET + ".rs")
    test = repo / "tests" / source.name
    manifest = repo / "crates/openhuman-cli/Cargo.toml"
    original = manifest.read_bytes()
    prior = test.read_bytes() if test.exists() else None
    if prior is not None and prior != source.read_bytes():
        raise SystemExit("Refusing to replace a different existing test.")
    if TARGET in original.decode() and DECL not in original.decode():
        raise SystemExit("Unexpected existing test target; inspect it first.")
    # Deliberate allowlist: no API keys, model tokens, proxy credentials or user app env are inherited.
    env = {
        "PATH": str(cargo.parent) + ":/usr/bin:/bin:/usr/sbin:/sbin",
        "CARGO_HOME": str(args.cargo_home.resolve()),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "RUST_MIN_STACK": "67108864",
        "RUST_BACKTRACE": "0",
        "OPENHUMAN_KEYRING_BACKEND": "file",
        "CI_CANCEL_WATCHDOG": "0",
    }
    receipt = {
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "base": BASE,
        "platform": platform.platform(),
        "submodules": submodules,
        "sourceStatusBefore": source_status,
        "runnerSHA256": digest(pathlib.Path(__file__)),
        "lockSHA256": digest(repo / "Cargo.lock"),
        "harnessSHA256": digest(source),
        "productionToolCalls": 0,
        "realCredentialsUsed": False,
        "modelCalls": 0,
        "networkPolicy": POLICY,
        "scope": "Native config RPC implementation + SQLite credential store + tinymcp HTTP + OpenHuman product tool factory + TinyAgents execute_tool_batch. Synthetic server and scheduled call; no desktop UI, model loop, orchestration handoff, hosted API, or production service.",
    }
    try:
        test.write_bytes(source.read_bytes())
        if DECL not in original.decode():
            manifest.write_bytes(original + DECL.encode())
        receipt["rustc"] = subprocess.check_output(
            [str(cargo.parent / "rustc"), "--version"], env=env, text=True
        ).strip()
        command = [
            "bash",
            "scripts/ci-cancel-aware.sh",
            str(cargo),
            "test",
            "--locked",
            "-p",
            "openhuman-cli",
            "--no-default-features",
            "--features",
            "mcp",
            "--test",
            TARGET,
            "--no-run",
            "--message-format=json",
        ]
        if not args.download_deps:
            command.append("--offline")
        receipt["buildCommand"] = command
        with (
            (out / "build.jsonl").open("w") as stdout,
            (out / "build.stderr.log").open("w") as stderr,
        ):
            result = subprocess.run(
                command, cwd=repo, env=env, stdout=stdout, stderr=stderr, check=False
            )
        receipt["buildExitCode"] = result.returncode
        if result.returncode:
            raise RuntimeError(
                "Native compilation failed; see build.stderr.log and build.jsonl."
            )
        executable = None
        for line in (out / "build.jsonl").read_text().splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                item.get("reason") == "compiler-artifact"
                and item.get("target", {}).get("name") == TARGET
                and item.get("executable")
            ):
                executable = item["executable"]
        if not executable:
            raise RuntimeError("Cargo did not report the native test executable.")
        # Test executable only: dependency retrieval/build are not confused with runtime isolation.
        command = [
            "/usr/bin/sandbox-exec",
            "-p",
            POLICY,
            executable,
            "--nocapture",
            "--test-threads=1",
        ]
        receipt["testCommand"] = command
        with (out / "tests.log").open("w") as log:
            result = subprocess.run(
                command,
                cwd=repo,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        receipt["testExitCode"] = result.returncode
        receipt["lockSHA256After"] = digest(repo / "Cargo.lock")
        if result.returncode:
            raise RuntimeError("Native validation failed; see tests.log.")
        if receipt["lockSHA256After"] != receipt["lockSHA256"]:
            raise RuntimeError("Lockfile changed.")
        receipt["outcome"] = "passed"
        print(
            "Native OpenHuman validation passed. See the receipt and tests.log for exact scope."
        )
    finally:
        manifest.write_bytes(original)
        if prior is None:
            test.unlink(missing_ok=True)
        else:
            test.write_bytes(prior)
        receipt["sourceStatusAfter"] = {"root": git(repo, "status", "--porcelain")}
        for line in submodules.splitlines():
            subpath = line[42:].rsplit(" (", 1)[0]
            receipt["sourceStatusAfter"][subpath] = git(
                repo / subpath, "status", "--porcelain"
            )
        receipt["finishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
