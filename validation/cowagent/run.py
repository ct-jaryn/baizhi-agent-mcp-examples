"""Run the pinned, synthetic CowAgent checks in a fresh temporary workspace."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


EXPECTED_HEAD = "e2a97497abbda2abf023cd5fec99b4613e94e5af"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", default=os.environ.get("COWAGENT_REPO"),
        help="CowAgent checkout path (or set COWAGENT_REPO)",
    )
    args = parser.parse_args()
    if not args.repo:
        parser.error("provide --repo or COWAGENT_REPO")
    if sys.version_info[:2] != (3, 12):
        parser.error("use Python 3.12 for this pinned validation environment")
    repo = Path(args.repo).expanduser().resolve()
    if not (repo / "agent/tools/mcp/mcp_client.py").is_file():
        parser.error("--repo must point to the CowAgent repository root")
    try:
        head = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True,
        ).strip()
        if head != EXPECTED_HEAD:
            parser.error("checkout the documented CowAgent commit: " + EXPECTED_HEAD)
        subprocess.run(
            ["git", "-C", str(repo), "diff", "--exit-code", "--quiet", "HEAD", "--",
             "agent", "common", "config.py"], check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        parser.error("Git must be available and the tested CowAgent source must be unchanged")

    test_file = Path(__file__).with_name("test_cowagent_mcp_host.py")
    with tempfile.TemporaryDirectory(prefix="cowagent-mcp-validation-") as temporary:
        scratch = Path(temporary)
        (scratch / "data").mkdir()
        pytest_config = scratch / "pytest.ini"
        pytest_config.write_text("[pytest]\n", encoding="utf-8")
        # Build a new environment. Do not inherit provider keys, proxies, HOME,
        # pytest plugins or a user's CowAgent configuration.
        env = {
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "PYTHONPATH": str(repo),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "COW_DATA_DIR": str(scratch / "data"),
        }
        if os.name == "nt" and "SYSTEMROOT" in os.environ:
            env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        print("CowAgent base: " + head, flush=True)
        print("Synthetic loopback only; no model or production calls.", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-s", "-c", str(pytest_config),
             "-p", "no:cacheprovider", "--basetemp", str(scratch / "pytest"), str(test_file)],
            cwd=scratch, env=env,
        )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
