import asyncio
import os
from gpt_researcher import GPTResearcher


async def main():
    api_key = os.environ["BAIZHI_API_KEY"].strip()
    if not api_key:
        raise ValueError("BAIZHI_API_KEY must not be empty")

    os.environ["RETRIEVER"] = "mcp"
    researcher = GPTResearcher(
        query="Find official documentation explaining MCP transports and authentication.",
        mcp_configs=[{
            "name": "baizhi",
            "connection_url": "https://agent-toolkit.app.baizhi.cloud/mcp",
            "connection_headers": {"Authorization": f"Bearer {api_key}"},
        }],
    )
    await researcher.conduct_research()
    report = await researcher.write_report()
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
