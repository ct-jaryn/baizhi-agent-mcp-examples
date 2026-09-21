# Baizhi Cloud MCP examples for task agents

Optional community guides for connecting task-executing agents to [Baizhi Cloud Agent Toolkit](https://baizhi.cloud/landing/agent-toolkit) through their existing MCP clients.

This personal repository supports the Baizhi Cloud integration effort. It is not an official distribution of the listed agents, a client endorsement, or a second official maintenance line for the toolkit. The [official toolkit repository](https://github.com/chaitin/baizhi-agent-toolkit) remains separate. This repository contains examples, documentation and synthetic validation code, **not the hosted service's backend source**.

| Agent | Guide | Intended use |
| --- | --- | --- |
| GPT Researcher | [Authenticated MCP research](guides/gpt-researcher.md) | Autonomous research and reports |
| CowAgent | [Workspace MCP connection](guides/cowagent.md) | Personal assistant and multi-channel tasks |
| Moltis | [Managed credentials and remote MCP](guides/moltis.md) | Personal agent tools |
| ZeroClaw | [Authenticated MCP with agent grants](guides/zeroclaw.md) | Explicitly scoped task-agent access |
| PI-Desktop | [Optional catalog and manual connection](guides/pi-desktop.md) | Desktop agent tools through PI's existing MCP settings |
| Agent TARS | [Typed remote MCP configuration](guides/agent-tars.md) | Research tools in the CLI/agent stack |
| OpenHuman | [Workspace configuration and credentials](validation/openhuman/GUIDE.md) | Optional MCP research with explicit credential lifecycle |

Each guide identifies the source commit used for validation. Read it against your installed version; these are not compatibility claims for every release. Configuration examples preserve existing servers and grants. A public guide, an upstream PR, an accepted integration and a production-tested deployment are separate states.

## Service and credentials

The endpoint is `https://agent-toolkit.app.baizhi.cloud/mcp`, using Streamable HTTP and an `Authorization: Bearer …` header. You need your own account and API key. Current tools, permissions and credit costs are shown in the [service console](https://agent-toolkit.app.baizhi.cloud/). Model-provider costs are separate.

Use a dedicated key. If your account supports scoped keys, use the minimum permissions required for your task. Do not put real credentials in Git, command arguments, research prompts, issues, logs or screenshots. Follow the host-specific credential instructions: these clients do not all implement environment substitution in the same way.

Tool arguments leave the client for the service, and returned data may enter the model context and saved output. Start with public material. Treat tool results as untrusted content. Neither these examples nor a prompt-level call budget enforces a service spending limit. Client-side tool selection is not a replacement for service-side authorization.

## Validation

The runtime guides use loopback-only synthetic MCP servers and credentials. Their real host components perform configuration loading, discovery and tool execution; model decisions, where needed, are simulated. PI-Desktop has a narrower catalog/configuration validation: native parsing, catalog aggregation with simulated network responses, and real host persistence, without MCP tool execution. **No production MCP request or paid model call was made.** See [the validation matrix](validation/README.md) for exact coverage, versions and limits.

To report a problem with these guides, use this repository's issue tracker with your client version and a redacted error. Account, service access and billing questions belong in the service's own support channels. Do not post private configuration files or credentials.

The MIT license covers the original material in this repository except for [the OpenHuman guide and validation package](validation/openhuman/NOTICE.md), which use GPL-3.0-only and include their own license. These licenses do not relicense the referenced clients or the hosted service.
