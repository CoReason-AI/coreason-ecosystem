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

from unittest.mock import patch

import mcp.types as types
import pytest

from coreason_ecosystem.storage.milvus_mcp import (
    MilvusSubstrateNotConfiguredError,
    query_vector_db,
)
from coreason_ecosystem.storage.neo4j_mcp import (
    Neo4jSubstrateNotConfiguredError,
    query_property_graph,
)


async def test_query_vector_db_raises_without_env() -> None:
    """Prove that query_vector_db raises when COREASON_MILVUS_URI is absent."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(
            MilvusSubstrateNotConfiguredError, match="COREASON_MILVUS_URI"
        ):
            await query_vector_db(
                collection_name="test_embeddings",
                query_vector=[0.1, 0.2, 0.3],
            )


async def test_query_property_graph_raises_without_env() -> None:
    """Prove that query_property_graph raises when COREASON_NEO4J_URI is absent."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(
            Neo4jSubstrateNotConfiguredError, match="COREASON_NEO4J_URI"
        ):
            await query_property_graph(cypher_query="MATCH (n) RETURN n")


async def test_query_vector_db_raises_not_implemented_with_env() -> None:
    """Prove that with URI set, query_vector_db reaches the driver TODO boundary."""
    with patch.dict("os.environ", {"COREASON_MILVUS_URI": "http://milvus:19530"}):
        with pytest.raises(NotImplementedError, match="Milvus driver execution"):
            await query_vector_db(
                collection_name="test_collection",
                query_vector=[1.0, 2.0],
            )


async def test_query_property_graph_raises_not_implemented_with_env() -> None:
    """Prove that with URI set, query_property_graph reaches the driver TODO boundary."""
    with patch.dict("os.environ", {"COREASON_NEO4J_URI": "bolt://neo4j:7687"}):
        with pytest.raises(NotImplementedError, match="Neo4j driver execution"):
            await query_property_graph(cypher_query="MATCH (n) RETURN n LIMIT 1")


async def test_milvus_call_tool_dispatches_correctly() -> None:
    """Prove the MCP call_tool dispatcher routes to query_vector_db."""
    from coreason_ecosystem.storage.milvus_mcp import call_tool

    with patch.dict("os.environ", {"COREASON_MILVUS_URI": "http://milvus:19530"}):
        with pytest.raises(NotImplementedError):
            await call_tool(
                "query_vector_db",
                {"collection_name": "test_collection", "query_vector": [1.0, 2.0]},
            )


async def test_neo4j_call_tool_dispatches_correctly() -> None:
    """Prove the MCP call_tool dispatcher routes to query_property_graph."""
    from coreason_ecosystem.storage.neo4j_mcp import call_tool

    with patch.dict("os.environ", {"COREASON_NEO4J_URI": "bolt://neo4j:7687"}):
        with pytest.raises(NotImplementedError):
            await call_tool(
                "query_property_graph",
                {"cypher_query": "MATCH (n) RETURN n LIMIT 1"},
            )


async def test_milvus_call_tool_rejects_unknown_tool() -> None:
    """Prove that the Milvus MCP rejects unknown tool names."""
    from coreason_ecosystem.storage.milvus_mcp import call_tool

    with pytest.raises(ValueError, match="Unknown tool"):
        await call_tool("nonexistent_tool", {})


async def test_neo4j_call_tool_rejects_unknown_tool() -> None:
    """Prove that the Neo4j MCP rejects unknown tool names."""
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
