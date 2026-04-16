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

Connection URI must be injected via COREASON_MILVUS_URI environment variable.
If the variable is absent, a configuration error is raised — the Governance
Plane is forbidden from returning fabricated substrate responses.
"""

import os
from typing import Any

import mcp.server
import mcp.types as types
from fastapi import FastAPI

app = FastAPI(title="coreason-milvus-mcp")
mcp_server = mcp.server.Server("coreason-milvus-mcp")


class MilvusSubstrateNotConfiguredError(RuntimeError):
    """Raised when the COREASON_MILVUS_URI environment variable is not set."""


def _require_milvus_uri() -> str:
    """Resolve the Milvus connection URI from the environment.

    Raises:
        MilvusSubstrateNotConfiguredError: if COREASON_MILVUS_URI is not set.
    """
    uri = os.environ.get("COREASON_MILVUS_URI")
    if not uri:
        raise MilvusSubstrateNotConfiguredError(
            "Substrate configuration error: COREASON_MILVUS_URI is not set. "
            "The Milvus Vector Substrate cannot be provisioned without a "
            "connection URI injected via secure .env hydration."
        )
    return uri


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

    Validates that the Milvus connection URI is present in the environment.
    If configured, the physical pymilvus driver execution belongs here.

    Args:
        collection_name: The Milvus collection to search.
        query_vector: The embedding vector to query against.

    Returns:
        A list containing a single TextContent with the search results.

    Raises:
        MilvusSubstrateNotConfiguredError: if COREASON_MILVUS_URI is not set.
    """
    milvus_uri = _require_milvus_uri()

    # TODO: Execute the vector search against the live Milvus instance using
    # pymilvus. The physical driver execution belongs here:
    #
    #   from pymilvus import MilvusClient
    #   client = MilvusClient(uri=milvus_uri)
    #   results = client.search(
    #       collection_name=collection_name,
    #       data=[query_vector],
    #       limit=10,
    #   )
    #
    # Authentication tokens must be hydrated from secure .env injection
    # via COREASON_MILVUS_TOKEN.
    _ = milvus_uri  # Consumed by the driver when implemented.
    _ = collection_name
    _ = query_vector
    raise NotImplementedError(
        f"Milvus driver execution pending implementation for URI: {milvus_uri}"
    )
