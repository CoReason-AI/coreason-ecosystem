"""
Neo4j Sub-MCP — Sovereign Storage gatekeeper for SemanticNodeState.

Zero-Trust boundary wrapper: swarm agents NEVER connect directly to Neo4j.
All property graph queries are mediated through this MCP tool interface.
"""

import json
from typing import Any

import mcp.server
import mcp.types as types
from fastapi import FastAPI

app = FastAPI(title="coreason-neo4j-mcp")
mcp_server = mcp.server.Server("coreason-neo4j-mcp")


@mcp_server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_tools() -> list[types.Tool]:
    """Expose the query_property_graph tool schema."""
    return [
        types.Tool(
            name="query_property_graph",
            description="Execute a Cypher query against the Neo4j property graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cypher_query": {
                        "type": "string",
                        "description": "The Cypher query to execute against the Neo4j database.",
                    },
                },
                "required": ["cypher_query"],
            },
        )
    ]


@mcp_server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Dispatch tool execution to the appropriate handler."""
    if name != "query_property_graph":
        raise ValueError(f"Unknown tool: {name}")

    return await query_property_graph(
        cypher_query=arguments["cypher_query"],
    )


async def query_property_graph(
    cypher_query: str,
) -> list[types.TextContent]:
    """
    Execute a Cypher query against the Neo4j property graph.

    In production this will use the neo4j driver to execute the query.
    Currently returns a simulated successful Cypher execution payload.

    Args:
        cypher_query: The Cypher query to execute.

    Returns:
        A list containing a single TextContent with the query results.
    """
    # Stub: simulated Neo4j Cypher execution result.
    simulated_result = {
        "status": "success",
        "cypher_query": cypher_query,
        "records": [
            {"n": {"label": "Concept", "id": "C0001", "name": "Aspirin"}},
            {"n": {"label": "Concept", "id": "C0002", "name": "Ibuprofen"}},
        ],
        "summary": {
            "nodes_created": 0,
            "relationships_created": 0,
            "properties_set": 0,
        },
    }

    return [types.TextContent(type="text", text=json.dumps(simulated_result))]
