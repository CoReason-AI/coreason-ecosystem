from mcp.server.sse import SseServerTransport
import inspect

methods = inspect.getmembers(SseServerTransport, predicate=inspect.isfunction)
for m in methods:
    print(m[0], inspect.signature(m[1]))
