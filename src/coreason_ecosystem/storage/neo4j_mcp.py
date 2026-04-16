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

Connection URI must be injected via COREASON_NEO4J_URI environment variable.
If the variable is absent, a configuration error is raised — the Governance
Plane is forbidden from returning fabricated substrate responses.
"""

import os
from typing import Any

import mcp.server
import mcp.types as types
from fastapi import FastAPI

app = FastAPI(title="coreason-neo4j-mcp")
mcp_server = mcp.server.Server("coreason-neo4j-mcp")


class Neo4jSubstrateNotConfiguredError(RuntimeError):
    """Raised when the COREASON_NEO4J_URI environment variable is not set."""


def _require_neo4j_uri() -> str:
    """Resolve the Neo4j connection URI from the environment.

    Raises:
        Neo4jSubstrateNotConfiguredError: if COREASON_NEO4J_URI is not set.
    """
    uri = os.environ.get("COREASON_NEO4J_URI")
    if not uri:
        raise Neo4jSubstrateNotConfiguredError(
            "Substrate configuration error: COREASON_NEO4J_URI is not set. "
            "The Neo4j Matrix Substrate cannot be provisioned without a "
            "connection URI injected via secure .env hydration."
        )
    return uri


@mcp_server.list_tools()  # type: ignore
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


@mcp_server.call_tool()  # type: ignore
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

    Validates that the Neo4j connection URI is present in the environment.
    If configured, the physical neo4j driver execution belongs here.

    Args:
        cypher_query: The Cypher query to execute.

    Returns:
        A list containing a single TextContent with the query results.

    Raises:
        Neo4jSubstrateNotConfiguredError: if COREASON_NEO4J_URI is not set.
    """
    neo4j_uri = _require_neo4j_uri()

    # TODO: Execute the Cypher query against the live Neo4j instance using
    # the neo4j async driver. The physical driver execution belongs here:
    #
    #   from neo4j import AsyncGraphDatabase
    #   async with AsyncGraphDatabase.driver(neo4j_uri, auth=(...)) as driver:
    #       async with driver.session() as session:
    #           result = await session.run(cypher_query)
    #           records = [dict(record) async for record in result]
    #
    # Credentials (username/password) must be hydrated from secure .env
    # injection via COREASON_NEO4J_USER and COREASON_NEO4J_PASSWORD.
    _ = neo4j_uri  # Consumed by the driver when implemented.
    raise NotImplementedError(
        f"Neo4j driver execution pending implementation for URI: {neo4j_uri}"
    )
