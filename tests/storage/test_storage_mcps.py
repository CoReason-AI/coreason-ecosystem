# Copyright (c) 2026 CoReason, Inc.
#
# This software is proprietary and dual-licensed
# Licensed under the Prosperity Public License 3.0 (the "License")
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file
# Commercial use beyond a 30-day trial requires a separate license
#
# Source Code: https://github.com/CoReason-AI/coreason-ecosystem

"""Tests for the Sovereign Storage Micro-MCPs — bounding proofs."""

import json

import mcp.types as types

from coreason_ecosystem.storage.milvus_mcp import query_vector_db
from coreason_ecosystem.storage.neo4j_mcp import query_property_graph


async def test_query_vector_db_returns_text_content() -> None:
    """Prove that query_vector_db returns a valid TextContent with passthrough results."""
    result = await query_vector_db(
        collection_name="test_embeddings",
        query_vector=[0.1, 0.2, 0.3, 0.4, 0.5],
    )

    assert len(result) == 1
    content = result[0]
    assert isinstance(content, types.TextContent)
    assert content.type == "text"

    payload = json.loads(content.text)
    assert payload["status"] == "passthrough"
    assert payload["collection"] == "test_embeddings"
    assert payload["query_dimensions"] == 5
    assert payload["matches"] == []


async def test_query_property_graph_returns_text_content() -> None:
    """Prove that query_property_graph returns a valid TextContent with passthrough results."""
    cypher = "MATCH (n:Concept) RETURN n LIMIT 10"
    result = await query_property_graph(cypher_query=cypher)

    assert len(result) == 1
    content = result[0]
    assert isinstance(content, types.TextContent)
    assert content.type == "text"

    payload = json.loads(content.text)
    assert payload["status"] == "passthrough"
    assert payload["cypher_query"] == cypher
    assert payload["records"] == []
    assert payload["summary"]["nodes_created"] == 0


async def test_milvus_call_tool_dispatches_correctly() -> None:
    """Prove the MCP call_tool dispatcher routes to query_vector_db."""
    from coreason_ecosystem.storage.milvus_mcp import call_tool

    result = await call_tool(
        "query_vector_db",
        {"collection_name": "test_collection", "query_vector": [1.0, 2.0]},
    )

    assert len(result) == 1
    payload = json.loads(result[0].text)
    assert payload["status"] == "passthrough"
    assert payload["collection"] == "test_collection"


async def test_neo4j_call_tool_dispatches_correctly() -> None:
    """Prove the MCP call_tool dispatcher routes to query_property_graph."""
    from coreason_ecosystem.storage.neo4j_mcp import call_tool

    result = await call_tool(
        "query_property_graph",
        {"cypher_query": "MATCH (n) RETURN n LIMIT 1"},
    )

    assert len(result) == 1
    payload = json.loads(result[0].text)
    assert payload["status"] == "passthrough"
    assert payload["cypher_query"] == "MATCH (n) RETURN n LIMIT 1"


async def test_milvus_call_tool_rejects_unknown_tool() -> None:
    """Prove that the Milvus MCP rejects unknown tool names."""
    import pytest

    from coreason_ecosystem.storage.milvus_mcp import call_tool

    with pytest.raises(ValueError, match="Unknown tool"):
        await call_tool("nonexistent_tool", {})


async def test_neo4j_call_tool_rejects_unknown_tool() -> None:
    """Prove that the Neo4j MCP rejects unknown tool names."""
    import pytest

    from coreason_ecosystem.storage.neo4j_mcp import call_tool

    with pytest.raises(ValueError, match="Unknown tool"):
        await call_tool("nonexistent_tool", {})


async def test_milvus_list_tools_returns_schema() -> None:
    """Prove that the Milvus MCP list_tools returns the expected tool schema."""
    from coreason_ecosystem.storage.milvus_mcp import list_tools

    tools = await list_tools()

    assert len(tools) == 1
    tool = tools[0]
    assert isinstance(tool, types.Tool)
    assert tool.name == "query_vector_db"
    assert "collection_name" in tool.inputSchema["properties"]
    assert "query_vector" in tool.inputSchema["properties"]


async def test_neo4j_list_tools_returns_schema() -> None:
    """Prove that the Neo4j MCP list_tools returns the expected tool schema."""
    from coreason_ecosystem.storage.neo4j_mcp import list_tools

    tools = await list_tools()

    assert len(tools) == 1
    tool = tools[0]
    assert isinstance(tool, types.Tool)
    assert tool.name == "query_property_graph"
    assert "cypher_query" in tool.inputSchema["properties"]
