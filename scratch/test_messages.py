from fastapi.testclient import TestClient
from coreason_ecosystem.gateway.master_mcp import app

client = TestClient(app)

response = client.get("/sse", headers={"Authorization": "Bearer token"})
print(response.status_code)

