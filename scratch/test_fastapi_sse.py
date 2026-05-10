import asyncio
import httpx
from coreason_ecosystem.gateway.master_mcp import app

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/sse")
        print(response.status_code, response.text)

asyncio.run(main())

