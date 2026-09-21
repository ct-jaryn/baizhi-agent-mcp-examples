# Baizhi Cloud MCP examples for task agents

Optional community guides for connecting task-executing agents to [Baizhi Cloud Agent Toolkit](https://baizhi.cloud/landing/agent-toolkit) through their existing MCP clients.

This personal repository supports the Baizhi Cloud integration effort. It is not an official distribution of the listed agents, a client endorsement, or a second official maintenance line for the toolkit. The [official toolkit repository](https://github.com/chaitin/baizhi-agent-toolkit) remains separate. This repository contains examples, documentation and synthetic validation code, **not the hosted service's backend source**.

| Agent | Guide | Intended use |
| --- | --- | --- |
| GPT Researcher | [Authenticated MCP research](guides/gpt-researcher.md) | Autonomous research and reports |
| CowAgent | [Workspace MCP connection](guides/cowagent.md) | Personal assistant and multi-channel tasks |
| Moltis | [Managed credentials and remote MCP](guides/moltis.md) | Personal agent tools |
| ZeroClaw | [Authenticated MCP with agent grants](guides/zeroclaw.md) | Explicitly scoped task-agent access |

Each guide identifies the source commit used for validation. Read it against your installed version; these are not compatibility claims for every release. Configuration examples preserve existing servers and grants. A public guide, an upstream PR, an accepted integration and a production-tested deployment are separate states.

## Service and credentials

The endpoint is `https://agent-toolkit.app.baizhi.cloud/mcp`, using Streamable HTTP and an `Authorization: Bearer …` header. You need your own account and API key. Current tools, permissions and credit costs are shown in the [service console](https://agent-toolkit.app.baizhi.cloud/). Model-provider costs are separate.

Use a dedicated key. If your account supports scoped keys, use the minimum permissions required for your task. Do not put real credentials in Git, command arguments, research prompts, issues, logs or screenshots. Follow the host-specific credential instructions: these clients do not all implement environment substitution in the same way.

Tool arguments leave the client for the service, and returned data may enter the model context and saved output. Start with public material. Treat tool results as untrusted content. Neither these examples nor a prompt-level call budget enforces a service spending limit. Client-side tool selection is not a replacement for service-side authorization.

## Validation

Validation uses loopback-only synthetic MCP servers and credentials. The real host components perform configuration loading, discovery and tool execution; model decisions, where needed, are simulated. **No production MCP request or paid model call was made.** See [the validation matrix](validation/README.md) for exact coverage, versions and limits.

To report a problem with these guides, use this repository's issue tracker with your client version and a redacted error. Account, service access and billing questions belong in the service's own support channels. Do not post private configuration files or credentials.

The MIT license covers the original material in this repository. It does not relicense the referenced clients or the hosted service.
