import asyncio
from fastapi import Request
from unittest.mock import AsyncMock

async def main():
    req = Request({"type": "http"}, receive=AsyncMock(), send=AsyncMock())
    print("scope:", req.scope)
    print("receive:", req.receive)

asyncio.run(main())

