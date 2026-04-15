import inspect
import mcp.server
from mcp.server.models import InitializationOptions

print("InitOptions signature:")
print(inspect.signature(InitializationOptions))
print(
    "Server.create_initialization_options exists?",
    hasattr(mcp.server.Server, "create_initialization_options"),
)
