"""
Milvus Sub-MCP — Sovereign Storage gatekeeper for VectorEmbeddingState.

Zero-Trust boundary wrapper: swarm agents NEVER connect directly to Milvus.
All vector queries are mediated through this MCP tool interface.
"""

import json
from typing import Any

import mcp.server
import mcp.types as types
from fastapi import FastAPI

app = FastAPI(title="coreason-milvus-mcp")
mcp_server = mcp.server.Server("coreason-milvus-mcp")


@mcp_server.list_tools()  # type: ignore[misc]
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


@mcp_server.call_tool()  # type: ignore[misc]
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
    """
    Query the Milvus vector database.

    In production this will use pymilvus to execute the search.
    Currently returns a simulated successful search payload.

    Args:
        collection_name: The Milvus collection to search.
        query_vector: The embedding vector to query against.

    Returns:
        A list containing a single TextContent with the search results.
    """
    # Stub: simulated Milvus vector search result.
    simulated_result = {
        "status": "success",
        "collection": collection_name,
        "query_dimensions": len(query_vector),
        "matches": [
            {
                "id": "vec-001",
                "score": 0.97,
                "metadata": {"label": "clinical_note_embeddings"},
            },
            {
                "id": "vec-002",
                "score": 0.91,
                "metadata": {"label": "fda_label_embeddings"},
            },
        ],
    }

    return [types.TextContent(type="text", text=json.dumps(simulated_result))]
