import asyncio
import httpx
from coreason_ecosystem.gateway.master_mcp import app

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        try:
            async with asyncio.timeout(1.0):
                response = await ac.get("/sse", headers={"Authorization": "Bearer token"})
        except asyncio.TimeoutError:
            print("Timeout, but it ran!")
        except Exception as e:
            print("Exception:", e)

asyncio.run(main())

