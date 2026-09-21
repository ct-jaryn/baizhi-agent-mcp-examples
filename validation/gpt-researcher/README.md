# Reproduce the local MCP validation

Use Python 3.12. Clone the upstream source and check out the exact commit:

```sh
git clone https://github.com/assafelovic/gpt-researcher.git gpt-researcher
git -C gpt-researcher checkout 6f998577d547b1e54ec662dac63583aa11e3b84b
python3.12 -m venv gptr-venv
gptr-venv/bin/python -m pip install -r validation/gpt-researcher/requirements-tested.txt
gptr-venv/bin/python -m pip install --no-deps -e ./gpt-researcher
python3 validation/gpt-researcher/run-validation.py ./gpt-researcher ./gptr-venv/bin/python
```

The runner uses an explicit environment allowlist and blocks non-loopback socket connections. Local port binding must be permitted. No real API key is needed. Logs and a command receipt are written next to the runner. Use an environment compatible with the pinned dependency versions; the recorded execution was macOS arm64, Python 3.12.14.

Result on 2026-09-21: **9 passed**, with two existing warnings (pytest configuration spelling and langchain-community deprecation). This exercises native MCP retrieval and tool execution with model decisions and remote data replaced by deterministic local fixtures. It does not run a full report-generation workflow with a live model.

The companion upstream documentation change also passed Python syntax, final-page MDX compilation and git diff checks. A full Docusaurus 3.7 build failed in both the unchanged baseline and the candidate due to webpackbar 6.0.1 / webpack 5.111.1 ProgressPlugin options; no unrelated dependency changes were included.
