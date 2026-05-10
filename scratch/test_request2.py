import asyncio
from fastapi import Request
from unittest.mock import AsyncMock

async def main():
    req = Request({"type": "http"}, receive=AsyncMock(), send=AsyncMock())
    print("_send:", req._send)

asyncio.run(main())

