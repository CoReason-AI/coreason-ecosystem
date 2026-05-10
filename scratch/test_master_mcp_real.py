import asyncio
from fastapi import Request, HTTPException
import pytest
from coreason_ecosystem.gateway.master_mcp import extract_and_verify_identity

@pytest.mark.asyncio
async def test_extract_missing():
    req = Request({"type": "http", "headers": []})
    try:
        await extract_and_verify_identity(req)
    except HTTPException as e:
        print("Missing:", e.status_code)

@pytest.mark.asyncio
async def test_extract_invalid():
    req = Request({"type": "http", "headers": [(b"authorization", b"Basic 1234")]})
    try:
        await extract_and_verify_identity(req)
    except HTTPException as e:
        print("Invalid:", e.status_code)

@pytest.mark.asyncio
async def test_extract_valid():
    req = Request({"type": "http", "headers": [(b"authorization", b"Bearer whatever_token")]})
    await extract_and_verify_identity(req)
    print("Valid: OK")

asyncio.run(test_extract_missing())
asyncio.run(test_extract_invalid())
asyncio.run(test_extract_valid())

