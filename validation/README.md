# Validation matrix

Recorded on 2026-09-21. Runtime checks are listed per host below. Agent TARS repeats its eight cases with two distinct client versions. PI-Desktop has nine catalog/configuration checks repeated against two source revisions. These counts do not represent products, a full application certification, or a live Baizhi acceptance run. Original test code is included to make the boundary reviewable.

| Host | Fixed upstream source | Passing checks | Reproduction |
| --- | --- | ---: | --- |
| GPT Researcher | `6f998577d547b1e54ec662dac63583aa11e3b84b` | 9: 5 native MCP/loopback + 4 existing configuration regressions | [Python 3.12.14, MCP 1.30.0, adapter 0.3.2](gpt-researcher/README.md) |
| CowAgent | `e2a97497abbda2abf023cd5fec99b4613e94e5af` | 10 native loading/dispatch/loopback checks | [Python 3.12.14, fixture MCP 1.26.0](cowagent/README.md) |
| Moltis | `9d3238c322708e9d57fe235ce1c2b43ccc33af62` | 6 native MCP/registry/bridge + 1 native configuration check | [Rust 1.98.1 and upstream lock](moltis/README.md) |
| ZeroClaw | `fba46e349b6bd084d43b721c7645525d2f5c597d` | 6 native config/grant/secret-store/registry/HTTP checks | [Rust 1.98.1 and upstream lock](zeroclaw/README.md) |
| PI-Desktop | main `b71fcf05a67dce5bb91c5fbd1f96f3a15fc8fe9a`; v0.15.1 `515620a4b7f6ce90df256e28d10d95957df16792` | 9 per revision: native catalog/configuration and host persistence; no MCP execution | [Node 24.21.0, TypeScript 5.9.3 and upstream locks](pi-desktop/README.md) |
| Agent TARS | `c2ad42e3eb9b27830db41a3e6f51ca7179d9b168` | 8 per client profile: native MCPAgent and ToolProcessor with client 1.2.20 and current source 1.2.29 | [Node 22.22.2, MCP SDK 1.15.1](agent-tars/README.md) |
| OpenHuman | `eb4fdc0f4f4a036d8ab7c12bd52f16128e4a6b5d` and recorded recursive submodules | 6 native configuration/store/tool-factory/TinyAgents scheduling cases | [Rust 1.96.1 and upstream lock; GPL-3.0-only](openhuman/README.md) |

The runtime guides execute real host components for configuration, transport and dispatch. Their remote MCP servers, credentials, tool schemas and returned data are synthetic. PI's checks execute its native catalog resolver and aggregator with simulated DNS/HTTPS responses, inspect renderer source contracts, and use separately built Rust hosts for configuration persistence; they do not execute the Electron UI or MCP transport. Where model decisions are needed, they are simulated; no paid model request is made. Runners isolate their state and do not require real service keys. Dependency installation can access public package registries; behavioral tests use local fixtures or simulated responses.

**Production MCP requests: 0. Live model calls: 0.** No GUI, complete user conversation, actual billing, current Baizhi account catalog, production TLS, or all-platform compatibility is certified. These tests also do not imply any upstream has accepted the integration.

A passing reproduction of an existing limitation is not a fix: CowAgent's pinned version ignores `disabled` and can wrap MCP call error text as a successful tool result. Pending upstream #3155 proposes disabled support. Moltis leaves unknown managed-environment placeholders literal and reads a single tool-list response. Guides describe those specific version boundaries.

The GPT Researcher candidate MDX page compiles, but its complete documentation site has a ProgressPlugin dependency error that also reproduces on the unchanged baseline. Moltis's seven checks used stable Rust rather than its declared nightly and do not satisfy its full upstream contribution gates. See each reproduction page for remaining limits and setup requirements.

Agent TARS checks feed synthetic calls into the real ToolProcessor; they do not run the complete agent loop. Its SDK close does not send session DELETE at the tested revision. OpenHuman uses its native product tool factory and TinyAgents tool-batch scheduler, but not the full session/approval middleware or `use_mcp_server` orchestration. See their package READMEs for exact boundaries.
