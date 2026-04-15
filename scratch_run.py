import inspect
import mcp.server

run_sig = inspect.signature(mcp.server.Server.run)
print(run_sig)
