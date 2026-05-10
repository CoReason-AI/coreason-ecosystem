import asyncio
import httpx
from coreason_ecosystem.gateway.master_mcp import app

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        try:
            async with ac.stream("GET", "/sse", headers={"Authorization": "Bearer token"}) as response:
                print(response.status_code)
                print(response.headers)
        except Exception as e:
            print("Exception:", e)

asyncio.run(main())

