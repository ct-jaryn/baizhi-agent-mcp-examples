# Validation matrix

Recorded on 2026-09-21. These are **32 focused checks**, not 32 products, a full application certification, or a live Baizhi acceptance run. Original test code is included to make the boundary reviewable.

| Host | Fixed upstream source | Passing checks | Reproduction |
| --- | --- | ---: | --- |
| GPT Researcher | `6f998577d547b1e54ec662dac63583aa11e3b84b` | 9: 5 native MCP/loopback + 4 existing configuration regressions | [Python 3.12.14, MCP 1.30.0, adapter 0.3.2](gpt-researcher/README.md) |
| CowAgent | `e2a97497abbda2abf023cd5fec99b4613e94e5af` | 10 native loading/dispatch/loopback checks | [Python 3.12.14, fixture MCP 1.26.0](cowagent/README.md) |
| Moltis | `9d3238c322708e9d57fe235ce1c2b43ccc33af62` | 6 native MCP/registry/bridge + 1 native configuration check | [Rust 1.98.1 and upstream lock](moltis/README.md) |
| ZeroClaw | `fba46e349b6bd084d43b721c7645525d2f5c597d` | 6 native config/grant/secret-store/registry/HTTP checks | [Rust 1.98.1 and upstream lock](zeroclaw/README.md) |

Real host components execute configuration, transport and dispatch. The remote MCP servers, credentials, tool schemas and returned data are synthetic. Where model decisions are needed, they are simulated; no paid model request is made. Runners isolate their state and do not require real service keys. Dependency installation can access public package registries; behavioral tests contact local fixtures.

**Production MCP requests: 0. Live model calls: 0.** No GUI, complete user conversation, actual billing, current Baizhi account catalog, production TLS, or all-platform compatibility is certified. These tests also do not imply any upstream has accepted the integration.

A passing reproduction of an existing limitation is not a fix: CowAgent's pinned version ignores `disabled` and can wrap MCP call error text as a successful tool result. Pending upstream #3155 proposes disabled support. Moltis leaves unknown managed-environment placeholders literal and reads a single tool-list response. Guides describe those specific version boundaries.

The GPT Researcher candidate MDX page compiles, but its complete documentation site has a ProgressPlugin dependency error that also reproduces on the unchanged baseline. Moltis's seven checks used stable Rust rather than its declared nightly and do not satisfy its full upstream contribution gates. See each reproduction page for remaining limits and setup requirements.
