// agent-tars.config.ts
import type { AgentTARSAppConfig } from "@agent-tars/interface";

const apiKey = process.env.BAIZHI_API_KEY?.trim();
if (!apiKey) {
  throw new Error("Set BAIZHI_API_KEY before starting Agent TARS");
}

export default {
  // Keep your existing model and other settings.
  mcpServers: {
    // Keep your existing MCP servers here.
    baizhi: {
      type: "streamable-http",
      url: "https://agent-toolkit.app.baizhi.cloud/mcp",
      headers: {
        Authorization: `Bearer ${apiKey}`,
      },
    },
  },
} satisfies AgentTARSAppConfig;
