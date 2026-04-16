# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Milvus Sub-MCP — Sovereign Storage gatekeeper for VectorEmbeddingState.

Zero-Trust boundary wrapper: swarm agents NEVER connect directly to Milvus.
All vector queries are mediated through this MCP tool interface.
This module is a domain-blind vector passthrough proxy — it routes queries
without inspecting or hardcoding semantic payloads.
"""

import json
from typing import Any

import mcp.server
import mcp.types as types
from fastapi import FastAPI

app = FastAPI(title="coreason-milvus-mcp")
mcp_server = mcp.server.Server("coreason-milvus-mcp")


@mcp_server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_tools() -> list[types.Tool]:
    """Expose the query_vector_db tool schema."""
    return [
        types.Tool(
            name="query_vector_db",
            description="Query the Milvus vector database for nearest-neighbor embeddings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {
                        "type": "string",
                        "description": "The Milvus collection to search.",
                    },
                    "query_vector": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "The embedding vector to query against.",
                    },
                },
                "required": ["collection_name", "query_vector"],
            },
        )
    ]


@mcp_server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Dispatch tool execution to the appropriate handler."""
    if name != "query_vector_db":
        raise ValueError(f"Unknown tool: {name}")

    return await query_vector_db(
        collection_name=arguments["collection_name"],
        query_vector=arguments["query_vector"],
    )


async def query_vector_db(
    collection_name: str,
    query_vector: list[float],
) -> list[types.TextContent]:
    """Query the Milvus vector database.

    In production this will use pymilvus to execute the search.
    Currently returns a domain-blind passthrough response echoing the
    collection name and query dimensions with an empty match set.

    Args:
        collection_name: The Milvus collection to search.
        query_vector: The embedding vector to query against.

    Returns:
        A list containing a single TextContent with the search results.
    """
    # Domain-blind passthrough: echoes query metadata with empty matches.
    # Production implementation connects to Milvus via credentials
    # hydrated from secure .env injection.
    passthrough_result = {
        "status": "passthrough",
        "collection": collection_name,
        "query_dimensions": len(query_vector),
        "matches": [],
    }

    return [types.TextContent(type="text", text=json.dumps(passthrough_result))]
