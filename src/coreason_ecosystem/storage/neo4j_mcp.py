# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Neo4j Sub-MCP — Sovereign Storage gatekeeper for SemanticNodeState.

Zero-Trust boundary wrapper: swarm agents NEVER connect directly to Neo4j.
All property graph queries are mediated through this MCP tool interface.
This module is a domain-blind Cypher passthrough proxy — it routes queries
without inspecting or hardcoding semantic payloads.
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
    """Execute a Cypher query against the Neo4j property graph.

    In production this will use the neo4j driver to execute the query.
    Currently returns a domain-blind passthrough response echoing the
    submitted Cypher query with an empty result set.

    Args:
        cypher_query: The Cypher query to execute.

    Returns:
        A list containing a single TextContent with the query results.
    """
    # Domain-blind passthrough: echoes query with empty results.
    # Production implementation connects to the Neo4j driver via
    # credentials hydrated from secure .env injection.
    passthrough_result = {
        "status": "passthrough",
        "cypher_query": cypher_query,
        "records": [],
        "summary": {
            "nodes_created": 0,
            "relationships_created": 0,
            "properties_set": 0,
        },
    }

    return [types.TextContent(type="text", text=json.dumps(passthrough_result))]
