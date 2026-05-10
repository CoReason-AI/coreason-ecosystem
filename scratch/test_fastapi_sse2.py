import asyncio
import httpx
from coreason_ecosystem.gateway.master_mcp import app

async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        try:
            async with ac.stream("GET", "/sse", headers={"Authorization": "Bearer valid"}) as response:
                print("Status code:", response.status_code)
                print("Headers:", response.headers)
                async for chunk in response.aiter_bytes():
                    print("Received chunk:", chunk)
                    break
        except Exception as e:
            print("Exception:", e)

asyncio.run(main())

